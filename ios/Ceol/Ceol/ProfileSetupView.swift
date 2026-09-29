// Profile setup after a first sign-in, the app's twin of /auth/setup-profile: a name
// and somewhere you play are required (the server's needs_profile_setup test — a first
// and last name, and at least one of city, state, country); time zone and instruments
// are optional. The form won't save what the server would still call incomplete.
//
// The Me tab opens the same form to edit the profile (`editing`): Cancel in place of
// Sign out, the account's time zone as it is, and it closes when saved.

import CeolAPI
import CeolDesign
import CeolSession
import SwiftUI

struct ProfileSetupView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    var editing = false
    var onSaved: () -> Void = {}

    @State private var loaded: Profile?
    @State private var firstName = ""
    @State private var lastName = ""
    @State private var city = ""
    @State private var state = ""
    @State private var country = ""
    @State private var timezone = TimeZone.current.identifier
    @State private var instruments: Set<String> = []
    // Editing from Me: the rest of the profile.
    @State private var username = ""
    @State private var sms = ""
    @State private var thesession = ""
    @State private var busy = false
    @State private var error: String?

    private func trimmed(_ s: String) -> String { s.trimmingCharacters(in: .whitespacesAndNewlines) }

    private var complete: Bool {
        !trimmed(firstName).isEmpty && !trimmed(lastName).isEmpty
            && !(trimmed(city).isEmpty && trimmed(state).isEmpty && trimmed(country).isEmpty)
    }

    var body: some View {
        NavigationStack {
            Form {
                if let loaded {
                    Section("Your name") {
                        TextField("First name", text: $firstName).textContentType(.givenName)
                        TextField("Last name", text: $lastName).textContentType(.familyName)
                    }
                    Section {
                        TextField("City", text: $city).textContentType(.addressCity)
                        TextField("State or county", text: $state).textContentType(.addressState)
                        TextField("Country", text: $country).textContentType(.countryName)
                    } header: {
                        Text("Where you play")
                    } footer: {
                        Text("At least one of these, so sessions near you make sense.")
                    }
                    if editing {
                        Section {
                            TextField("Username", text: $username)
                                .textInputAutocapitalization(.never).autocorrectionDisabled()
                            TextField("SMS number", text: $sms).keyboardType(.phonePad).textContentType(.telephoneNumber)
                            TextField("thesession.org member number or link", text: $thesession)
                                .textInputAutocapitalization(.never).autocorrectionDisabled()
                        } header: {
                            Text("Account")
                        } footer: {
                            Text("Your thesession.org member number is in your profile's address there: thesession.org/members/1234.")
                        }
                    }
                    Section("Time zone") {
                        Picker("Time zone", selection: $timezone) {
                            ForEach(timezoneChoices(loaded), id: \.value) { Text($0.label).tag($0.value) }
                        }
                    }
                    Section("Instruments (optional)") {
                        ForEach(loaded.canonicalInstruments, id: \.self) { name in
                            Button {
                                if instruments.contains(name) { instruments.remove(name) } else { instruments.insert(name) }
                            } label: {
                                HStack {
                                    Text(name).foregroundStyle(CeolTokens.textColor)
                                    Spacer()
                                    if instruments.contains(name) {
                                        Image(systemName: "checkmark").foregroundStyle(CeolTokens.primary)
                                    }
                                }
                            }
                        }
                    }
                    if let error {
                        Section { Text(error).foregroundStyle(CeolTokens.danger) }
                    }
                } else if let error {
                    Section {
                        Text(error).foregroundStyle(CeolTokens.danger)
                        Button("Try again") { Task { await load() } }
                    }
                } else {
                    ProgressView()
                }
            }
            .scrollContentBackground(.hidden)
            .background(CeolTokens.bgColor)
            .navigationTitle(editing ? "Edit profile" : "Your profile")
            .navigationBarTitleDisplayMode(editing ? .inline : .automatic)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { Task { await save() } }
                        .disabled(!complete || busy || loaded == nil)
                        .accessibilityIdentifier("profile.save")
                }
                ToolbarItem(placement: .cancellationAction) {
                    if editing {
                        Button("Cancel") { dismiss() }
                    } else {
                        Button("Sign out", role: .destructive) { Task { await model.signOut() } }
                    }
                }
            }
            .task { await load() }
        }
    }

    /// The server's list, plus this device's zone when the list doesn't have it.
    private func timezoneChoices(_ p: Profile) -> [Components.Schemas.Option] {
        var options = p.timezoneOptions
        if !options.contains(where: { $0.value == timezone }) {
            options.insert(.init(value: timezone, label: timezone), at: 0)
        }
        return options
    }

    private func load() async {
        error = nil
        do {
            let p = try await model.auth.profile()
            firstName = p.profile.firstName
            lastName = p.profile.lastName
            city = p.profile.city
            state = p.profile.state
            country = p.profile.country
            // Keep the account's zone; at first setup, unless it is still the default and
            // the device knows better.
            if !p.profile.timezone.isEmpty && (editing || p.profile.timezone != "UTC") { timezone = p.profile.timezone }
            instruments = Set(p.profile.instruments)
            username = p.account?.username ?? ""
            sms = p.profile.smsNumber ?? ""
            thesession = p.profile.thesessionUserId.map(String.init) ?? ""
            loaded = p
        } catch {
            self.error = "Couldn't load your profile. Check your connection and try again."
        }
    }

    private func save() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            let saved = try await model.auth.updateProfile(
                .init(
                    firstName: trimmed(firstName), lastName: trimmed(lastName), city: trimmed(city),
                    state: trimmed(state), country: trimmed(country), timezone: timezone,
                    instruments: instruments.sorted(),
                    smsNumber: editing ? trimmed(sms) : nil,
                    thesessionUserId: editing ? trimmed(thesession) : nil,
                    username: editing && !trimmed(username).isEmpty ? trimmed(username) : nil))
            if saved.needsProfileSetup {
                error = "That's not quite everything: a first and last name, and somewhere you play."
            } else {
                await model.profileSaved()
                onSaved()
                if editing { dismiss() }
            }
        } catch let f as AuthFailure {
            error = f.message
        } catch {
            self.error = "Couldn't save. Check your connection and try again."
        }
    }
}
