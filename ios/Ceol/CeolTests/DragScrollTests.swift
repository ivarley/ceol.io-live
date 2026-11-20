// Dragging a tune in the night's log: where the log scrolls while a drag is held near
// its edge, and how fast (never over the cap, however far past the edge). The web's
// rules (frontend/tests/dragscroll.test.js).

import Foundation
import Testing
@testable import Ceol

@MainActor
struct DragScrollTests {
    let visible: ClosedRange<CGFloat> = 100...700

    @Test func noEdgeInTheMiddle() {
        #expect(DragScroll.edge(400, visible: visible) == nil)
        #expect(DragScroll.edge(100 + DragScroll.zone, visible: visible) == nil)
        #expect(DragScroll.edge(700 - DragScroll.zone, visible: visible) == nil)
    }

    @Test func deeperTowardTheEdgeAndNoDeeperBeyondIt() {
        let half = DragScroll.edge(100 + DragScroll.zone / 2, visible: visible)
        #expect(half?.edge == .top && half?.depth == 0.5)
        #expect(DragScroll.edge(-500, visible: visible)?.depth == 1)
        let under = DragScroll.edge(2000, visible: visible)
        #expect(under?.edge == .bottom && under?.depth == 1)
    }

    @Test func aShortLogKeepsAMiddle() {
        #expect(DragScroll.edge(45, visible: 0...90) == nil)
        #expect(DragScroll.edge(10, visible: 0...90)?.edge == .top)
    }

    @Test func speedStartsSlowAndNeverPassesTheCap() {
        #expect(DragScroll.speed(0) == DragScroll.minSpeed)
        #expect(DragScroll.speed(0.5) < (DragScroll.minSpeed + DragScroll.maxSpeed) / 2)
        #expect(DragScroll.speed(1) == DragScroll.maxSpeed)
        #expect(DragScroll.speed(40) == DragScroll.maxSpeed)
    }
}
