// Generated from design/tokens.json by scripts/build_tokens.py. Do not edit.
//
// The web reads these from CSS custom properties; this is the same source
// rendered for Swift, so the two clients cannot drift apart by hand.

import SwiftUI

public enum CeolTokens {

    // MARK: - Colors

    public static let blue = Color(red: 0.0000, green: 0.4824, blue: 1.0000)  // #007bff
    public static let indigo = Color(red: 0.4000, green: 0.0627, blue: 0.9490)  // #6610f2
    public static let purple = Color(red: 0.4353, green: 0.2588, blue: 0.7569)  // #6f42c1
    public static let pink = Color(red: 0.9098, green: 0.2431, blue: 0.5490)  // #e83e8c
    public static let red = Color(red: 0.8627, green: 0.2078, blue: 0.2706)  // #dc3545
    public static let orange = Color(red: 0.9922, green: 0.4941, blue: 0.0784)  // #fd7e14
    public static let yellow = Color(red: 1.0000, green: 0.7569, blue: 0.0275)  // #ffc107
    public static let green = Color(red: 0.1569, green: 0.6549, blue: 0.2706)  // #28a745
    public static let teal = Color(red: 0.1255, green: 0.7882, blue: 0.5922)  // #20c997
    public static let cyan = Color(red: 0.0902, green: 0.6353, blue: 0.7216)  // #17a2b8
    public static let white = Color(red: 1.0000, green: 1.0000, blue: 1.0000)  // #fff
    public static let gray = Color(red: 0.6784, green: 0.7059, blue: 0.7529)  // #adb4c0
    public static let grayDark = Color(red: 0.4549, green: 0.4980, blue: 0.5804)  // #747f94
    /// The wordmark's own green, sampled from static/images/logo3-1.png. The accent family below is this hue (119deg) lifted for a dark background — at 3.7:1 on --bg-color the mark's own green is fine as a mark and too dark for text.
    public static let logoGreen = Color(red: 0.2902, green: 0.5020, blue: 0.2863)  // #4a8049
    /// The logo hue at the legibility the old grey had (4.9:1, same as #888): resting tab-bar labels and anywhere else that wants the brand colour without shouting.
    public static let logoGreenSoft = Color(red: 0.3373, green: 0.5882, blue: 0.3294)  // #569654
    /// Accent TEXT, links, icons and thin borders. The logo hue at 6.9:1 on --bg-color, which is where the blue it replaced sat (6.8:1). It is too light to sit BEHIND white text — that is --primary-fill's job.
    public static let primary = Color(red: 0.3961, green: 0.7059, blue: 0.3922)  // #65b464
    /// Accent FILL: every surface that carries white text — a selected filter, a tune-type chip, a primary button. The logo green itself, sampled from logo3-1.png, which is one flat #4a8049. White on it is 4.69:1; white on the lighter --primary was 2.54:1, under AA, and read as the washed-out green a phone uses for the messages it does not want you to like.
    public static let primaryFill = Color(red: 0.2902, green: 0.5020, blue: 0.2863)  // #4a8049
    public static let secondary = Color(red: 0.5412, green: 0.5843, blue: 0.6588)  // #8a95a8
    public static let success = Color(red: 0.3020, green: 0.6863, blue: 0.3529)  // #4daf5a
    public static let info = Color(red: 0.3569, green: 0.6000, blue: 0.9176)  // #5b99ea
    public static let warning = Color(red: 0.9608, green: 0.7843, blue: 0.2588)  // #f5c842
    public static let danger = Color(red: 0.9098, green: 0.3529, blue: 0.3529)  // #e85a5a
    public static let light = Color(red: 0.1765, green: 0.1765, blue: 0.1765)  // #2d2d2d
    public static let dark = Color(red: 0.8784, green: 0.8784, blue: 0.8784)  // #e0e0e0
    /// Theme surface/text variables (the app is dark-only)
    public static let bgColor = Color(red: 0.1020, green: 0.1020, blue: 0.1020)  // #1a1a1a
    public static let textColor = Color(red: 0.8784, green: 0.8784, blue: 0.8784)  // #e0e0e0
    public static let headerBg = Color(red: 0.1765, green: 0.1765, blue: 0.1765)  // #2d2d2d
    public static let borderColor = Color(red: 0.2667, green: 0.2667, blue: 0.2667)  // #444
    public static let dropdownBg = Color(red: 0.1765, green: 0.1765, blue: 0.1765)  // #2d2d2d
    public static let dropdownBorder = Color(red: 0.2667, green: 0.2667, blue: 0.2667)  // #444
    public static let hoverBg = Color(red: 0.2392, green: 0.2392, blue: 0.2392)  // #3d3d3d
    public static let disabledText = Color(red: 0.5333, green: 0.5333, blue: 0.5333)  // #888
    public static let hamburgerLineColor = Color(red: 0.8784, green: 0.8784, blue: 0.8784)  // #e0e0e0
    public static let successBg = Color(red: 0.1765, green: 0.3529, blue: 0.1961)  // #2d5a32
    public static let successBorder = Color(red: 0.2392, green: 0.4314, blue: 0.2588)  // #3d6e42
    public static let successText = Color(red: 0.5647, green: 0.9333, blue: 0.5647)  // #90ee90
    public static let errorBg = Color(red: 0.3529, green: 0.1765, blue: 0.1765)  // #5a2d2d
    public static let errorBorder = Color(red: 0.4314, green: 0.2392, blue: 0.2392)  // #6e3d3d
    public static let errorText = Color(red: 1.0000, green: 0.7020, blue: 0.7020)  // #ffb3b3
    public static let warningBg = Color(red: 0.3529, green: 0.2902, blue: 0.1765)  // #5a4a2d
    public static let warningBorder = Color(red: 0.4314, green: 0.3529, blue: 0.2392)  // #6e5a3d
    public static let warningText = Color(red: 1.0000, green: 0.8431, blue: 0.0000)  // #ffd700
    public static let infoBg = Color(red: 0.1765, green: 0.2902, blue: 0.3529)  // #2d4a5a
    public static let infoBorder = Color(red: 0.2392, green: 0.3686, blue: 0.4314)  // #3d5e6e
    public static let infoText = Color(red: 0.7020, green: 0.8784, blue: 1.0000)  // #b3e0ff
    public static let linkColor = Color(red: 0.3961, green: 0.7059, blue: 0.3922)  // #65b464
    public static let linkHoverColor = Color(red: 0.5725, green: 0.7922, blue: 0.5686)  // #92ca91
    public static let inputBg = Color(red: 0.1765, green: 0.1765, blue: 0.1765)  // #2d2d2d
    public static let secondaryText = Color(red: 0.5333, green: 0.5333, blue: 0.5333)  // #888
    public static let tableHeaderBg = Color(red: 0.2392, green: 0.2392, blue: 0.2392)  // #3d3d3d
    /// Muted text (formerly a phantom var)
    public static let textMuted = Color(red: 0.5333, green: 0.5333, blue: 0.5333)  // #888
    /// Hover-state darks (formerly phantom vars; values match the fallbacks in use)
    public static let primaryDark = Color(red: 0.2392, green: 0.5255, blue: 0.2353)  // #3d863c
    /// --primary-fill hovered: 10% darker. White text 5.57:1, and still 3.12:1 against the page, so a hovered chip does not sink into the background. --primary-dark is NOT this — it is lighter than --primary-fill, so using it here would brighten on hover.
    public static let primaryFillHover = Color(red: 0.2627, green: 0.4510, blue: 0.2588)  // #437342
    public static let secondaryDark = Color(red: 0.3529, green: 0.3843, blue: 0.4078)  // #5a6268
    /// Already-added rows in tune search
    public static let alreadyAddedBg = Color(red: 0.2275, green: 0.2275, blue: 0.2275)  // #3a3a3a
    public static let alreadyAddedHoverBg = Color(red: 0.2706, green: 0.2706, blue: 0.2706)  // #454545
    /// Modal surfaces (moved from tune_detail_modal.css so load order doesn't matter)
    public static let modalBgSecondary = Color(red: 0.1647, green: 0.1647, blue: 0.1647)  // #2a2a2a
    public static let modalTextMuted = Color(red: 0.5333, green: 0.5333, blue: 0.5333)  // #888
    public static let modalPrimaryDark = Color(red: 0.2863, green: 0.6196, blue: 0.2784)  // #499e47

    // MARK: - Lengths — radii, spacing, fixed heights

    /// The site header is position:fixed at this height on every width, so anything that sticks to the top of the viewport has to start BELOW it or it slides underneath and disappears. Named here rather than repeated as a magic 42.
    public static let siteHeaderH = CGFloat(42)
    /// Radius
    public static let rSm = CGFloat(4)
    public static let r = CGFloat(8)
    public static let rLg = CGFloat(12)
    public static let rPill = CGFloat(999)
    /// Spacing: 4px base scale
    public static let sp1 = CGFloat(4)
    public static let sp2 = CGFloat(8)
    public static let sp3 = CGFloat(12)
    public static let sp4 = CGFloat(16)
    public static let sp5 = CGFloat(20)
    public static let sp6 = CGFloat(24)
    public static let sp7 = CGFloat(28)
    public static let sp8 = CGFloat(32)

    // MARK: - Motion

    /// Motion
    public static let durQuick = Double(0.15)
    public static let dur = Double(0.25)

    // MARK: - Z-order

    /// Tier 1: component layering (1-10)
    public static let zBackground = Double(-1)
    public static let zBase = Double(0)
    public static let zComponent1 = Double(1)
    public static let zComponent2 = Double(2)
    public static let zComponent3 = Double(3)
    public static let zComponentElevated = Double(10)
    /// Tier 2: reserved for Bootstrap framework elements — do not reuse
    public static let zBootstrapDropdown = Double(1000)
    public static let zBootstrapSticky = Double(1020)
    public static let zBootstrapFixed = Double(1030)
    public static let zBootstrapModalBackdrop = Double(1040)
    public static let zBootstrapModal = Double(1050)
    public static let zBootstrapPopover = Double(1060)
    public static let zBootstrapTooltip = Double(1070)
    /// Tier 3: application UI. Modals sit BELOW the header (2000) on purpose, so the hamburger menu stays accessible while a modal is open.
    public static let zModalOverlay = Double(1900)
    public static let zModalContent = Double(1910)
    public static let zModalSidebar = Double(1920)
    public static let zDragGhost = Double(1930)
    public static let zHeader = Double(2000)
    public static let zHamburgerDropdown = Double(2010)
    public static let zInSessionPopup = Double(2020)
    /// Kit Sheet/Dialog (spec 035): full-screen sheet chrome carries its own header (Cancel/title/Done), so unlike the legacy modals it must cover the fixed header. Search dropdowns (2100) still float above sheets.
    public static let zSheetOverlay = Double(2030)
    public static let zSheetContent = Double(2040)
    public static let zSearchDropdown = Double(2100)
    public static let zContextMenu = Double(2500)
    public static let zLoadingOverlay = Double(2800)
    public static let zPullToRefresh = Double(2850)
    /// Tier 4: top layer — toasts only
    public static let zToast = Double(9999)
}

// Not represented here, because Swift has no useful equivalent: font stacks,
// multi-part shadows, rgba() scrims and CSS breakpoints. They stay CSS-only.
//
// breakpoint-lg, breakpoint-md, breakpoint-sm, breakpoint-xl, breakpoint-xs, dropdown-shadow
// ease, font-family-monospace, font-family-sans-serif, scrim, shadow-lg, shadow-md
// shadow-sm
