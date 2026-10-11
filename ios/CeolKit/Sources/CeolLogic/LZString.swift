// lz-string's compressToEncodedURIComponent (pieroxy's LZString 1.4.4), ported so the
// app can build the same abc-tools links the web does (tunesheet/logic.js abcToolsUrl):
// michaeleskin.com reads the ABC from the URL's lzw= parameter in exactly this form.
// Works on UTF-16 code units, as the JavaScript does, so the output matches it byte
// for byte. Held to the web's output in LZStringTests.

import Foundation

public enum LZString {
    private static let uriSafeKey: [Character] = Array(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-$")

    /// The text, compressed, in characters safe inside a URL query.
    public static func compressToEncodedURIComponent(_ input: String) -> String {
        compress(input, bitsPerChar: 6) { uriSafeKey[$0] }
    }

    private static func compress(_ uncompressed: String, bitsPerChar: Int, getChar: (Int) -> Character) -> String {
        let units = Array(uncompressed.utf16)
        if units.isEmpty { return "" }
        // Keyed by UTF-16 units, not Strings: a lone surrogate half is a unit of its own
        // here, as in JavaScript, and a String could not hold it.
        var dictionary: [[UInt16]: Int] = [:]
        var dictionaryToCreate: Set<[UInt16]> = []
        var w: [UInt16] = []
        var enlargeIn = 2
        var dictSize = 3
        var numBits = 2
        var data: [Character] = []
        var dataVal = 0
        var dataPosition = 0

        func push(_ value: Int, bits: Int) {
            var v = value
            for _ in 0..<bits {
                dataVal = (dataVal << 1) | (v & 1)
                if dataPosition == bitsPerChar - 1 {
                    dataPosition = 0
                    data.append(getChar(dataVal))
                    dataVal = 0
                } else {
                    dataPosition += 1
                }
                v >>= 1
            }
        }

        func emit(_ w: [UInt16]) {
            if dictionaryToCreate.contains(w) {
                let c = Int(w[0])
                if c < 256 {
                    push(0, bits: numBits)
                    push(c, bits: 8)
                } else {
                    push(1, bits: numBits)
                    push(c, bits: 16)
                }
                enlargeIn -= 1
                if enlargeIn == 0 {
                    enlargeIn = 1 << numBits
                    numBits += 1
                }
                dictionaryToCreate.remove(w)
            } else {
                push(dictionary[w]!, bits: numBits)
            }
            enlargeIn -= 1
            if enlargeIn == 0 {
                enlargeIn = 1 << numBits
                numBits += 1
            }
        }

        for unit in units {
            let c = [unit]
            if dictionary[c] == nil {
                dictionary[c] = dictSize
                dictSize += 1
                dictionaryToCreate.insert(c)
            }
            let wc = w + c
            if dictionary[wc] != nil {
                w = wc
            } else {
                emit(w)
                dictionary[wc] = dictSize
                dictSize += 1
                w = c
            }
        }

        if !w.isEmpty {
            emit(w)
        }

        // The end marker.
        push(2, bits: numBits)

        // Flush.
        while true {
            dataVal <<= 1
            if dataPosition == bitsPerChar - 1 {
                data.append(getChar(dataVal))
                break
            }
            dataPosition += 1
        }
        return String(data)
    }
}
