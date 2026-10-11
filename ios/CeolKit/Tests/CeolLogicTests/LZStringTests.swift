import Testing

@testable import CeolLogic

/// The port of lz-string's compressToEncodedURIComponent, held to what the web's
/// lz-string 1.4.4 produces for the same text (generated with node and pasted here),
/// since michaeleskin.com's abc-tools reads the ABC from the URL in exactly this form.
struct LZStringTests {
    @Test("an ABC tune compresses as the web does")
    func abc() {
        let abc = "X: 1\nT: Drowsy Maggie\nR: Reel\nM: 4/4\nL: 1/8\nK: Edor\n|:E2BE dEBE|E2BE AFDF|E2BE dEBE|BABc dAFD:|\n|:d2fd c2ec|defg afge|d2fd c2ec|BABc dAFD:|"
        #expect(LZString.compressToEncodedURIComponent(abc)
            == "BoLgBAjAUAKuAiAnA9gdwM4E8wFkCGA5gQJYCmUASuBaaQDZQ7gAsA9M1ADLgSsAcUANLgAogBNkiKAB8QIgEwAhEWDEjl0hcrABBAGLw9mpSrUbFOxQGNV++CGkyQY+QDMxYK-NJXpY0q4EYHiBpH5uHl4+0hbWtgYOQA")
    }

    @Test("short and non-ASCII text, a surrogate pair included")
    func shortAndUnicode() {
        #expect(LZString.compressToEncodedURIComponent("abc") == "IYIwxkA")
        #expect(LZString.compressToEncodedURIComponent("Pádraig ♪ 𝄞") == "AoQ4JgTghglg5gAkFZkDAsG4PF2g")
        #expect(LZString.compressToEncodedURIComponent("") == "")
    }
}
