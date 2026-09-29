// The web's look, for the app: Poppins, the web's colours, the wordmark, and the small
// set of pieces the web kit draws everywhere (the type chip, pills, section headings,
// the date block, the status glyph, underlined tabs, the set card). Screens use these
// rather than styling themselves, as the web's pages use frontend/src/lib, so the two
// clients stay alike as either changes.

import CeolDesign
import CoreText
import SwiftUI
import UIKit

// MARK: - Poppins

/// The web's font (frontend/src/app.css: "the app-wide font"), bundled in Fonts/ under
/// the SIL Open Font License (Fonts/OFL.txt). Registered at launch; no Info.plist entry.
enum CeolFont {
    static func register() {
        for weight in ["Light", "Regular", "Medium", "SemiBold", "Bold", "Italic"] {
            guard let url = Bundle.main.url(forResource: "Poppins-\(weight)", withExtension: "ttf") else { continue }
            CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil)
        }
    }

    static func name(_ weight: Font.Weight) -> String {
        switch weight {
        case .light, .thin, .ultraLight: "Poppins-Light"
        case .medium: "Poppins-Medium"
        case .semibold: "Poppins-SemiBold"
        case .bold, .heavy, .black: "Poppins-Bold"
        default: "Poppins-Regular"
        }
    }

    /// Point sizes for each text style. Poppins sets larger than SF at the same size,
    /// so these sit a step under Apple's defaults, near the web's px sizes.
    static func size(_ style: Font.TextStyle) -> CGFloat {
        switch style {
        case .largeTitle: 30
        case .title: 26
        case .title2: 22
        case .title3: 19
        case .headline: 16
        case .callout: 15
        case .subheadline: 14
        case .footnote: 13
        case .caption: 12
        case .caption2: 11
        default: 16
        }
    }

    static func ui(_ size: CGFloat, _ weight: Font.Weight = .regular) -> UIFont {
        UIFont(name: name(weight), size: size) ?? .systemFont(ofSize: size)
    }
}

extension Font {
    /// Poppins at a text style's size, scaling with Dynamic Type.
    static func ceol(_ style: Font.TextStyle = .body, weight: Font.Weight? = nil) -> Font {
        let w = weight ?? (style == .headline ? .semibold : .regular)
        return .custom(CeolFont.name(w), size: CeolFont.size(style), relativeTo: style)
    }

    /// Poppins Italic (the web's notes and asides).
    static func ceolItalic(size: CGFloat, relativeTo style: Font.TextStyle = .body) -> Font {
        .custom("Poppins-Italic", size: size, relativeTo: style)
    }

    /// Poppins at an exact size (the web's px), still scaling with Dynamic Type.
    static func ceol(size: CGFloat, weight: Font.Weight = .regular, relativeTo style: Font.TextStyle = .body) -> Font {
        .custom(CeolFont.name(weight), size: size, relativeTo: style)
    }
}

// MARK: - UIKit appearance

enum CeolAppearance {
    /// The bars and controls SwiftUI draws with UIKit: Poppins, and the web's greens.
    static func apply() {
        let nav = UINavigationBarAppearance()
        nav.configureWithDefaultBackground()
        nav.titleTextAttributes = [.font: CeolFont.ui(17, .semibold), .foregroundColor: UIColor(CeolTokens.textColor)]
        nav.largeTitleTextAttributes = [.font: CeolFont.ui(30, .semibold), .foregroundColor: UIColor(CeolTokens.textColor)]
        let button = UIBarButtonItemAppearance()
        button.normal.titleTextAttributes = [.font: CeolFont.ui(16, .medium)]
        nav.buttonAppearance = button
        nav.doneButtonAppearance = button
        UINavigationBar.appearance().standardAppearance = nav
        UINavigationBar.appearance().compactAppearance = nav
        let scrollEdge = nav.copy()
        scrollEdge.configureWithTransparentBackground()
        UINavigationBar.appearance().scrollEdgeAppearance = scrollEdge

        // The web's bar: every tab in the logo's green, the current one in the full accent.
        let tab = UITabBarAppearance()
        tab.configureWithDefaultBackground()
        for layout in [tab.stackedLayoutAppearance, tab.inlineLayoutAppearance, tab.compactInlineLayoutAppearance] {
            layout.normal.iconColor = UIColor(CeolTokens.logoGreenSoft)
            layout.normal.titleTextAttributes = [.font: CeolFont.ui(10, .medium), .foregroundColor: UIColor(CeolTokens.logoGreenSoft)]
            layout.selected.iconColor = UIColor(CeolTokens.primary)
            layout.selected.titleTextAttributes = [.font: CeolFont.ui(10, .semibold), .foregroundColor: UIColor(CeolTokens.primary)]
        }
        UITabBar.appearance().standardAppearance = tab
        UITabBar.appearance().scrollEdgeAppearance = tab
        UITabBar.appearance().unselectedItemTintColor = UIColor(CeolTokens.logoGreenSoft)

        // Segmented controls fill the chosen segment green, as the web's do.
        let seg = UISegmentedControl.appearance()
        seg.selectedSegmentTintColor = UIColor(CeolTokens.primaryFill)
        seg.setTitleTextAttributes([.font: CeolFont.ui(14), .foregroundColor: UIColor(CeolTokens.textColor)], for: .normal)
        seg.setTitleTextAttributes([.font: CeolFont.ui(14, .medium), .foregroundColor: UIColor.white], for: .selected)

        UISearchTextField.appearance().font = CeolFont.ui(16)
        UITextField.appearance().font = CeolFont.ui(16)
    }
}

// MARK: - Page chrome

extension View {
    /// A tab's root screen, as the web's pages look: the green "ceol" wordmark top-left
    /// (it goes Home, as the web's does), Share top-right, and no page heading. `title`
    /// still names the screen for the back button; `sharePath` is the page on the web.
    func ceolRootBar(_ title: String, sharePath: String) -> some View {
        navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { WordmarkButton() }
                    .sharedBackgroundVisibility(.hidden)
                ToolbarItem(placement: .principal) { Color.clear.frame(width: 1, height: 1) }
                ToolbarItem(placement: .topBarTrailing) { ShareButton(path: sharePath, subject: title) }
                    .sharedBackgroundVisibility(.hidden)
            }
            .ceolHeaderBar()
    }

    /// The web's header strip: the top bar on the header colour, always.
    func ceolHeaderBar() -> some View {
        toolbarBackground(CeolTokens.headerBg, for: .navigationBar)
            .toolbarBackgroundVisibility(.visible, for: .navigationBar)
            // The system tab bar stays hidden on every screen; MainTabView draws the web's.
            .toolbarVisibility(.hidden, for: .tabBar)
    }

    /// The web's list rows: edge to edge on the page background, hairline dividers.
    func ceolPlainList() -> some View {
        listStyle(.plain)
            .scrollContentBackground(.hidden)
            .background(CeolTokens.bgColor)
    }

    /// A plain-list row on the page background, with the web's padding.
    func ceolRow() -> some View {
        listRowBackground(CeolTokens.bgColor)
            .listRowSeparatorTint(CeolTokens.borderColor)
            .listRowInsets(EdgeInsets(top: 8, leading: 16, bottom: 8, trailing: 16))
    }
}

// MARK: - The kit

/// The tune-type chip: solid logo green, white text (the web's .tune-type).
struct TypeChip: View {
    let label: String
    var size: CGFloat = 13

    var body: some View {
        Text(label.capitalized)
            .font(.ceol(size: size))
            .lineLimit(1)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(CeolTokens.primaryFill, in: RoundedRectangle(cornerRadius: 3))
            .foregroundStyle(.white)
    }
}

/// A rounded pill: outlined ("Today", "Starts 7:00pm") or filled ("On Now", "Admin").
struct Pill: View {
    enum Style { case outline, filled }
    let text: String
    var style: Style = .outline
    var color: Color = CeolTokens.textMuted
    var size: CGFloat = 13

    var body: some View {
        let shape = Capsule()
        Text(text)
            .font(.ceol(size: size, weight: .medium))
            .lineLimit(1)
            .padding(.horizontal, 10)
            .padding(.vertical, 3)
            .foregroundStyle(style == .filled ? .white : color)
            .background(style == .filled ? AnyShapeStyle(color) : AnyShapeStyle(.clear), in: shape)
            .overlay(shape.strokeBorder(style == .outline ? color.opacity(0.7) : .clear, lineWidth: 1))
    }
}

/// A section's heading, as the web's Home draws them: a green icon, a bold title, an
/// optional trailing link, and a rule underneath.
struct SectionHeading<Trailing: View>: View {
    let title: String
    var icon: String? = nil
    @ViewBuilder var trailing: () -> Trailing

    var body: some View {
        VStack(spacing: 8) {
            HStack(spacing: 10) {
                if let icon {
                    Image(icon).renderingMode(.template).resizable().scaledToFit().frame(width: 22, height: 22)
                        .foregroundStyle(CeolTokens.primary)
                }
                Text(title).font(.ceol(size: 22, weight: .semibold, relativeTo: .title2)).foregroundStyle(CeolTokens.textColor)
                Spacer()
                trailing()
            }
            Rectangle().fill(CeolTokens.borderColor).frame(height: 1)
        }
    }
}

extension SectionHeading where Trailing == EmptyView {
    init(title: String, icon: String? = nil) {
        self.init(title: title, icon: icon) { EmptyView() }
    }
}

/// The web's date block: the weekday in small capitals over the day of the month.
struct DateBlock: View {
    let weekday: String
    let day: String
    var color: Color = CeolTokens.primary

    var body: some View {
        VStack(spacing: 0) {
            Text(weekday.uppercased()).font(.ceol(size: 12, weight: .medium, relativeTo: .caption))
                .foregroundStyle(CeolTokens.textMuted)
            Text(day).font(.ceol(size: 26, weight: .semibold, relativeTo: .title)).foregroundStyle(color)
        }
        .frame(width: 44)
    }
}

/// The learn status as the web's phone list shows it: learned ✓ green, learning ⋯
/// orange, want to learn ● blue.
struct StatusGlyph: View {
    let status: String

    var body: some View {
        let (glyph, color): (String, Color) =
            switch status {
            case "learned": ("✓", Color(red: 0.36, green: 0.72, blue: 0.36))
            case "learning": ("⋯", Color(red: 0.94, green: 0.68, blue: 0.31))
            default: ("●", Color(red: 0.36, green: 0.75, blue: 0.87))
            }
        Text(glyph)
            .font(.system(size: status == "want to learn" ? 11 : 17, weight: .bold))
            .foregroundStyle(color)
            .frame(width: 20)
            .accessibilityLabel(MyTunesStatusLabel.label(status))
    }
}

enum MyTunesStatusLabel {
    static func label(_ status: String) -> String {
        switch status {
        case "learned": "Learned"
        case "learning": "Learning"
        default: "To Learn"
        }
    }
}

/// The web's underlined tabs (a session's Tunes / Logs / People): the current one green
/// with a green rule, the counts muted.
struct UnderlineTabs<ID: Hashable>: View {
    let items: [(id: ID, label: String, count: Int?)]
    @Binding var selection: ID

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 0) {
                ForEach(items, id: \.id) { item in
                    let on = item.id == selection
                    Button {
                        selection = item.id
                    } label: {
                        VStack(spacing: 8) {
                            HStack(alignment: .firstTextBaseline, spacing: 5) {
                                Text(item.label).font(.ceol(size: 19, weight: .medium, relativeTo: .title3))
                                    .foregroundStyle(on ? CeolTokens.primary : CeolTokens.textMuted)
                                if let count = item.count {
                                    Text("\(count)").font(.ceol(size: 14)).foregroundStyle(CeolTokens.textMuted)
                                }
                            }
                            Rectangle().fill(on ? CeolTokens.primary : .clear).frame(height: 3)
                        }
                        .frame(maxWidth: .infinity)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(item.count.map { "\(item.label) \($0)" } ?? item.label)
                    .accessibilityAddTraits(on ? .isSelected : [])
                }
            }
            Rectangle().fill(CeolTokens.borderColor).frame(height: 1)
        }
    }
}

/// A set of a night's log, as the web draws it: a card, its tune type in small
/// capitals on the top edge, and who started it on the right.
struct SetCard<Content: View>: View {
    let label: String
    var starter: String? = nil
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 18)
        .padding(.top, 20)
        .padding(.bottom, 10)
        .background(CeolTokens.headerBg.opacity(0.6), in: RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(CeolTokens.borderColor.opacity(0.6), lineWidth: 1))
        .overlay(alignment: .topLeading) {
            if !label.isEmpty { edgeTag(label.uppercased(), letterSpacing: 1.2).offset(x: 14, y: -12) }
        }
        .overlay(alignment: .topTrailing) {
            if let starter { edgeTag("▸ \(starter)", letterSpacing: 0).offset(x: -14, y: -12) }
        }
        .padding(.top, 12)
    }

    private func edgeTag(_ text: String, letterSpacing: CGFloat) -> some View {
        Text(text)
            .font(.ceol(size: 12, weight: .semibold, relativeTo: .caption))
            .tracking(letterSpacing)
            .foregroundStyle(CeolTokens.textColor.opacity(0.85))
            .padding(.horizontal, 10)
            .padding(.vertical, 4)
            .background(CeolTokens.bgColor, in: Capsule())
            .overlay(Capsule().strokeBorder(CeolTokens.borderColor, lineWidth: 1))
    }
}

/// A muted count box (the web's play-count square next to a type chip).
struct CountBox: View {
    let count: Int

    var body: some View {
        Text("\(count)")
            .font(.ceol(size: 13, weight: .medium))
            .frame(minWidth: 22)
            .padding(.vertical, 2)
            .background(Color(white: 0.4), in: RoundedRectangle(cornerRadius: 3))
            .foregroundStyle(.white)
    }
}

/// Initials in a green circle (the web's profile avatar).
struct InitialsAvatar: View {
    let first: String
    let last: String
    var size: CGFloat = 64

    var body: some View {
        Text((first.prefix(1) + last.prefix(1)).uppercased())
            .font(.ceol(size: size * 0.36, weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: size, height: size)
            .background(CeolTokens.primaryFill, in: Circle())
    }
}

/// The web's toolbar row (lib/Toolbar.svelte): a search field, then square outlined
/// buttons for the filter menu and for adding.
struct SearchRow<FilterMenu: View>: View {
    @Binding var text: String
    let prompt: String
    var fieldID: String = "search"
    var filterActive = false
    @ViewBuilder var filterMenu: () -> FilterMenu
    var onAdd: (() -> Void)? = nil
    var addID: String = "add"
    var addLabel: String = "Add"
    var focused: FocusState<Bool>.Binding? = nil
    /// Opens a sort and filter drawer (in place of the menu); `filterCount` badges it.
    var onFilter: (() -> Void)? = nil
    var filterCount = 0

    var body: some View {
        HStack(spacing: 10) {
            TextField("", text: $text, prompt: Text(prompt).foregroundStyle(CeolTokens.textMuted))
                .font(.ceol(size: 17))
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .submitLabel(.search)
                .padding(.horizontal, 12)
                .frame(height: 46)
                .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
                .overlay(alignment: .trailing) {
                    if !text.isEmpty {
                        Button { text = "" } label: {
                            Image(systemName: "xmark.circle.fill").foregroundStyle(CeolTokens.textMuted)
                        }
                        .buttonStyle(.borderless)
                        .padding(.trailing, 10)
                        .accessibilityLabel("Clear")
                    }
                }
                .accessibilityIdentifier(fieldID)
                .modifier(OptionalFocus(focused: focused))
            if let onFilter {
                Button(action: onFilter) {
                    square(Image(systemName: "slider.vertical.3"), color: filterCount > 0 ? CeolTokens.primary : CeolTokens.textColor)
                        .overlay(alignment: .topTrailing) {
                            if filterCount > 0 {
                                Text("\(filterCount)").font(.ceol(size: 11, weight: .semibold)).foregroundStyle(.white)
                                    .frame(minWidth: 18, minHeight: 18)
                                    .background(CeolTokens.primaryFill, in: Circle())
                                    .offset(x: 6, y: -6)
                            }
                        }
                }
                // Borderless: in a List row, plain buttons share the row's tap, and the
                // filter button's tap opened Add (and the reverse).
                .buttonStyle(.borderless)
                .accessibilityLabel(filterCount > 0 ? "Sort and filter, \(filterCount) on" : "Sort and filter")
                .accessibilityIdentifier("\(fieldID).filter")
            } else if FilterMenu.self != EmptyView.self {
                Menu { filterMenu() } label: {
                    square(Image(systemName: "slider.vertical.3"), color: filterActive ? CeolTokens.primary : CeolTokens.textColor)
                }
                .accessibilityLabel("Filter")
            }
            if let onAdd {
                Button(action: onAdd) { square(Image(systemName: "plus"), color: CeolTokens.primary) }
                    .buttonStyle(.borderless)
                    .accessibilityLabel(addLabel)
                    .accessibilityIdentifier(addID)
            }
        }
    }

    private func square(_ image: Image, color: Color) -> some View {
        image.font(.system(size: 19, weight: .medium))
            .foregroundStyle(color)
            .frame(width: 46, height: 46)
            .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(CeolTokens.borderColor, lineWidth: 1))
            .contentShape(Rectangle())
    }
}

private struct OptionalFocus: ViewModifier {
    let focused: FocusState<Bool>.Binding?
    func body(content: Content) -> some View {
        if let focused { content.focused(focused) } else { content }
    }
}

extension SearchRow where FilterMenu == EmptyView {
    init(text: Binding<String>, prompt: String, fieldID: String = "search", onAdd: (() -> Void)? = nil,
         addID: String = "add", addLabel: String = "Add", focused: FocusState<Bool>.Binding? = nil,
         onFilter: (() -> Void)? = nil, filterCount: Int = 0) {
        self.init(text: text, prompt: prompt, fieldID: fieldID, filterMenu: { EmptyView() }, onAdd: onAdd,
                  addID: addID, addLabel: addLabel, focused: focused, onFilter: onFilter, filterCount: filterCount)
    }
}

/// A thin divider in the border colour.
struct Hairline: View {
    var body: some View { Rectangle().fill(CeolTokens.borderColor).frame(height: 1) }
}

extension View {
    /// A pushed screen's top bar: the back button and actions on the header colour,
    /// no centred title (the web puts the name on the page).
    func ceolPushedBar(_ title: String) -> some View {
        navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .principal) { Color.clear.frame(width: 1, height: 1) } }
            .ceolHeaderBar()
    }
}

/// The web kit's grouped rows (lib/grouped.css): a rounded card of rows with dividers,
/// each a label on the left and its value on the right, and an optional small-capitals
/// heading above.
struct KitGroup<Content: View>: View {
    var title: String? = nil
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let title {
                Text(title.uppercased()).font(.ceol(size: 13, weight: .semibold)).tracking(1)
                    .foregroundStyle(CeolTokens.textMuted)
                    .padding(.leading, 20)
            }
            VStack(spacing: 0) {
                Group(subviews: content()) { rows in
                    ForEach(Array(rows.enumerated()), id: \.offset) { i, row in
                        row
                        if i < rows.count - 1 { Hairline().padding(.leading, 20) }
                    }
                }
            }
            .background(CeolTokens.headerBg, in: RoundedRectangle(cornerRadius: 12))
        }
    }
}

/// One row of a KitGroup.
struct KitRow<Trailing: View>: View {
    let label: String
    var labelColor: Color = CeolTokens.textColor
    @ViewBuilder var trailing: () -> Trailing

    var body: some View {
        HStack(spacing: 12) {
            Text(label).font(.ceol(size: 18)).foregroundStyle(labelColor)
            Spacer(minLength: 8)
            trailing()
        }
        .padding(.horizontal, 20)
        .frame(minHeight: 54)
        .contentShape(Rectangle())
    }
}

extension KitRow where Trailing == Text {
    init(_ label: String, value: String, muted: Bool = false) {
        self.init(label: label) {
            Text(value).font(.ceol(size: 18)).foregroundStyle(muted ? CeolTokens.textMuted : CeolTokens.textColor)
        }
    }
}


/// The wordmark, which takes you Home.
struct WordmarkButton: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        Button { model.tab = .home } label: {
            Image("Wordmark").resizable().scaledToFit().frame(width: 110, height: 42)
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Ceol, go to Home")
        .accessibilityIdentifier("wordmark")
    }
}

/// The web's Share (its glyph, muted): the system share sheet with this page's address
/// on the web, for someone without the app too.
struct ShareButton: View {
    @Environment(AppModel.self) private var model
    let path: String
    var subject: String = "Ceol"

    var body: some View {
        ShareLink(item: model.webURL(path), subject: Text(subject)) {
            Image("IconShare").renderingMode(.template).resizable().scaledToFit().frame(width: 20, height: 20)
                .foregroundStyle(CeolTokens.textMuted)
                .frame(width: 36, height: 36)
                .contentShape(Rectangle())
        }
        .accessibilityLabel("Share")
    }
}


extension View {
    /// A drawer: a lighter surface than the page under it, and the grabber that says it
    /// can be dragged away.
    func ceolDrawer(_ detents: Set<PresentationDetent> = [.large]) -> some View {
        presentationDetents(detents)
            .presentationDragIndicator(.visible)
            .presentationBackground(CeolTokens.drawerBg)
    }
}

extension CeolTokens {
    /// A drawer's surface: a step lighter than the page (#1a1a1a) and the cards on it.
    static let drawerBg = Color(red: 0.17, green: 0.17, blue: 0.17)
}

/// A labelled row of choices in a drawer: the label above, the chips wrapping below.
struct ChoiceChips<ID: Hashable>: View {
    let label: String
    let options: [(id: ID, label: String)]
    @Binding var selection: ID

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label.uppercased()).font(.ceol(size: 12, weight: .semibold)).tracking(0.8)
                .foregroundStyle(CeolTokens.textMuted)
            FlowLayout(spacing: 8) {
                ForEach(options, id: \.id) { opt in
                    let on = opt.id == selection
                    Button { selection = opt.id } label: {
                        Text(opt.label).font(.ceol(size: 15, weight: on ? .semibold : .regular))
                            .padding(.horizontal, 14).padding(.vertical, 7)
                            .foregroundStyle(on ? .white : CeolTokens.textColor)
                            .background(on ? CeolTokens.primaryFill : .clear, in: Capsule())
                            .overlay(Capsule().strokeBorder(on ? .clear : CeolTokens.borderColor, lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                    .accessibilityAddTraits(on ? .isSelected : [])
                }
            }
        }
    }
}

/// Lays its children left to right, wrapping onto new lines.
struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, line: CGFloat = 0, widest: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x > 0 && x + s.width > width {
                y += line + spacing
                x = 0
                line = 0
            }
            x += s.width + spacing
            line = max(line, s.height)
            widest = max(widest, x - spacing)
        }
        return CGSize(width: min(widest, width), height: y + line)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, line: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x > bounds.minX && x + s.width > bounds.maxX {
                y += line + spacing
                x = bounds.minX
                line = 0
            }
            v.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(s))
            x += s.width + spacing
            line = max(line, s.height)
        }
    }
}
