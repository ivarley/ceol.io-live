// A night's details (spec 052 §B15), from the header, as the web's "Log details" sheet
// (frontend/src/App.svelte): the date and times (Change), the name (Rename), the tunes,
// the status (Mark complete / Re-open), who's attending (Manage) and who's logging, the
// notes (editable), and the way back to the session. Every change here needs a
// connection, as on the web; each saves on its own.

import CeolDesign
import CeolLogic
import SwiftUI

struct LogDetailsSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(AppModel.self) private var app
    let model: NightModel
    let onManageAttendance: () -> Void

    @State private var notes = ""
    @State private var notesSaving = false
    @State private var why: String?
    @State private var editingDate = false
    @State private var editingName = false
    @State private var confirmComplete = false
    @State private var confirmReopen = false

    var body: some View {
        let meta = model.log?.meta ?? [:]
        let complete = meta["log_complete"] == true
        NavigationStack {
            List {
                Section {
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text("Date").foregroundStyle(CeolTokens.textMuted)
                            Spacer()
                            Button("Change") { editingDate = true }.accessibilityIdentifier("details.date")
                        }
                        Text(whenLabel(meta)).foregroundStyle(CeolTokens.textColor)
                    }
                    row("Name", meta["instance_name"]?.stringValue.flatMap { $0.isEmpty ? nil : $0 } ?? unnamed) {
                        Button(meta["instance_name"]?.stringValue?.isEmpty == false ? "Rename" : "Name it") { editingName = true }
                            .accessibilityIdentifier("details.name")
                    }
                    row("Tunes", tuneSummary) { EmptyView() }
                    row("Status", complete ? "✓ Marked complete" : "Still logging") {
                        if complete {
                            Button("Re-open") { confirmReopen = true }.accessibilityIdentifier("details.reopen")
                        } else {
                            Button("Mark complete") { confirmComplete = true }.accessibilityIdentifier("details.complete")
                        }
                    }
                }
                if model.trackAttendance || !model.roster.isEmpty {
                    Section("Who and what") {
                        NightPeopleDetails(model: model) {
                            dismiss()
                            onManageAttendance()
                        }
                    }
                }
                Section("Notes") {
                    TextField("Add notes for this session…", text: $notes, axis: .vertical)
                        .lineLimit(3...8)
                        .accessibilityIdentifier("details.notes")
                    if notes != (meta["notes"]?.stringValue ?? "") {
                        HStack {
                            Button(notesSaving ? "Saving…" : "Save") {
                                notesSaving = true
                                Task {
                                    let r = await model.metaOp("edit_notes", ["notes": .string(notes)], label: "notes")
                                    why = r.why
                                    notesSaving = false
                                }
                            }
                            .disabled(notesSaving)
                            .accessibilityIdentifier("details.saveNotes")
                            Spacer()
                            Button("Cancel") { notes = meta["notes"]?.stringValue ?? "" }.foregroundStyle(CeolTokens.textMuted)
                        }
                        .buttonStyle(.borderless)
                    }
                }
                if let why {
                    Text(why).foregroundStyle(CeolTokens.errorText)
                }
                if let path = model.night?["session_path"]?.stringValue {
                    Section {
                        Button {
                            dismiss()
                            app.openSession(path: path, name: model.night?["session_name"]?.stringValue ?? "")
                        } label: {
                            HStack {
                                Text(model.night?["session_name"]?.stringValue ?? "The session").foregroundStyle(CeolTokens.textColor)
                                Spacer()
                                Image(systemName: "chevron.right").foregroundStyle(CeolTokens.textMuted)
                            }
                        }
                        .accessibilityIdentifier("details.session")
                    }
                }
            }
            .font(.ceol(size: 16))
            .scrollContentBackground(.hidden)
            .background(CeolTokens.drawerBg)
            .navigationTitle("Log details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() }.accessibilityIdentifier("details.done") }
            }
            .sheet(isPresented: $editingDate) { DateEditor(model: model) }
            .sheet(isPresented: $editingName) { NameEditor(model: model) }
            .confirmationDialog("Mark this session log as completely logged?", isPresented: $confirmComplete, titleVisibility: .visible) {
                Button("Mark complete") { Task { why = await model.markComplete() } }
            } message: {
                Text("This hides the editing controls.")
            }
            .confirmationDialog("Re-open this session log for editing?", isPresented: $confirmReopen, titleVisibility: .visible) {
                Button("Re-open log") { Task { why = await model.reopen() } }
            }
        }
        .ceolDrawer([.large])
        .onAppear { notes = meta["notes"]?.stringValue ?? "" }
    }

    /// A weekly session's unnamed night is "the usual"; at a festival there is no usual.
    private var unnamed: String {
        model.night?["session_type"]?.stringValue == "festival" ? "Unnamed" : "The usual"
    }

    private var tuneSummary: String {
        guard let log = model.log else { return "" }
        let sets = LogState.segmentByBreaks(log.ordered)
        let n = sets.reduce(0) { $0 + $1.tunes.count }
        if n == 0 { return "None yet" }
        return "\(n) tune\(n == 1 ? "" : "s") in \(sets.count) set\(sets.count == 1 ? "" : "s")"
    }

    private func whenLabel(_ meta: [String: JSONValue]) -> String {
        let when = HomeRules.instanceTimeLabel(start: meta["start_time"]?.stringValue, end: meta["end_time"]?.stringValue)
        return (meta["session_date"]?.stringValue ?? "—") + (when.isEmpty ? "" : " · \(when)")
    }

    private func row(_ key: String, _ value: String, @ViewBuilder action: () -> some View) -> some View {
        HStack {
            Text(key).foregroundStyle(CeolTokens.textMuted).frame(width: 70, alignment: .leading)
            Text(value).foregroundStyle(CeolTokens.textColor).lineLimit(2)
            Spacer()
            action()
        }
    }
}

/// Re-date the log (spec 046): mostly for a night logged past midnight, so "Previous
/// day" is first; a picker for anything else; the start and end times; Save.
struct DateEditor: View {
    @Environment(\.dismiss) private var dismiss
    let model: NightModel
    @State private var date = Date()
    @State private var hasStart = false
    @State private var start = Date()
    @State private var hasEnd = false
    @State private var end = Date()
    @State private var why: String?
    @State private var confirm = false
    @State private var saving = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    HStack {
                        Button { shift(-1) } label: { Label("Previous day", systemImage: "chevron.left") }
                        Spacer()
                        Button { shift(1) } label: { Label("Next day", systemImage: "chevron.right").labelStyle(TrailingIcon()) }
                    }
                    .buttonStyle(.borderless)
                    DatePicker("Date", selection: $date, displayedComponents: .date)
                }
                Section("Time") {
                    Toggle("Start time", isOn: $hasStart)
                    if hasStart { DatePicker("Starts", selection: $start, displayedComponents: .hourAndMinute) }
                    Toggle("End time", isOn: $hasEnd)
                    if hasEnd { DatePicker("Ends", selection: $end, displayedComponents: .hourAndMinute) }
                }
                if let why {
                    Text(why).foregroundStyle(CeolTokens.errorText)
                }
            }
            .scrollContentBackground(.hidden)
            .background(CeolTokens.drawerBg)
            .navigationTitle("Change the date")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(saving ? "Saving…" : confirm ? "Save anyway" : "Save") { Task { await save() } }
                        .disabled(saving)
                        .accessibilityIdentifier("date.save")
                }
            }
        }
        .ceolDrawer([.large])
        .onAppear(perform: load)
    }

    private static func fmt(_ f: String) -> DateFormatter {
        let d = DateFormatter()
        d.calendar = Calendar(identifier: .gregorian)
        d.locale = Locale(identifier: "en_US_POSIX")
        d.dateFormat = f
        return d
    }

    private func load() {
        let meta = model.log?.meta ?? [:]
        if let d = meta["instance_date"]?.stringValue.flatMap(Self.fmt("yyyy-MM-dd").date(from:)) { date = d }
        if let s = meta["start_time"]?.stringValue, !s.isEmpty, let t = Self.fmt("HH:mm").date(from: String(s.prefix(5))) {
            hasStart = true
            start = t
        }
        if let e = meta["end_time"]?.stringValue, !e.isEmpty, let t = Self.fmt("HH:mm").date(from: String(e.prefix(5))) {
            hasEnd = true
            end = t
        }
    }

    private func shift(_ days: Int) {
        date = Calendar.current.date(byAdding: .day, value: days, to: date) ?? date
        confirm = false
        why = nil
    }

    private func save() async {
        saving = true
        defer { saving = false }
        // Date and times in one op: one edit, one Save, one history row.
        let r = await model.metaOp(
            "set_date",
            [
                "date": .string(Self.fmt("yyyy-MM-dd").string(from: date)),
                "start_time": hasStart ? .string(Self.fmt("HH:mm").string(from: start)) : .string(""),
                "end_time": hasEnd ? .string(Self.fmt("HH:mm").string(from: end)) : .string(""),
                "confirm": .bool(confirm),
            ], label: "changing the date")
        if let w = r.why {
            why = w
            // Another log on that date is allowed, just rarely meant: offer to go ahead.
            confirm = r.answer?["reason"] == "date_conflict"
            return
        }
        dismiss()
    }
}

private struct TrailingIcon: LabelStyle {
    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 4) {
            configuration.title
            configuration.icon
        }
    }
}

/// Name the log (a festival's sessions share a date; the name tells them apart).
struct NameEditor: View {
    @Environment(\.dismiss) private var dismiss
    let model: NightModel
    @State private var name = ""
    @State private var why: String?
    @State private var saving = false

    var body: some View {
        NavigationStack {
            Form {
                TextField("Name this log", text: $name).accessibilityIdentifier("name.field")
                if let why { Text(why).foregroundStyle(CeolTokens.errorText) }
            }
            .scrollContentBackground(.hidden)
            .background(CeolTokens.drawerBg)
            .navigationTitle("Name this log")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(saving ? "Saving…" : "Save") {
                        saving = true
                        Task {
                            let next = name.trimmingCharacters(in: .whitespaces)
                            if next == (model.log?.meta["instance_name"]?.stringValue ?? "") {
                                dismiss()
                                return
                            }
                            let r = await model.metaOp("set_name", ["name": .string(next)], label: "naming this log")
                            saving = false
                            if let w = r.why { why = w } else { dismiss() }
                        }
                    }
                    .disabled(saving)
                    .accessibilityIdentifier("name.save")
                }
            }
        }
        .ceolDrawer([.medium])
        .onAppear { name = model.log?.meta["instance_name"]?.stringValue ?? "" }
    }
}
