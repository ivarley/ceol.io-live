// Where the sign-in token lives. The token is a user_session id: a Bearer token the
// server issues at login (spec 052 A1), valid until logout or six weeks idle. It is a
// credential, so on a device it goes in the Keychain, never in UserDefaults.

import Foundation
import Security
import Synchronization

public protocol TokenStore: Sendable {
    /// The current token, or nil when signed out.
    func token() -> String?
    /// Store a token, or remove it with nil.
    func setToken(_ token: String?) throws
}

/// The Keychain, as a generic password readable only while the device is unlocked
/// and never synced or restored to another device: a new device signs in again.
public struct KeychainTokenStore: TokenStore {
    public let service: String
    public let account: String

    public init(service: String = "io.ceol.Ceol", account: String = "session-token") {
        self.service = service
        self.account = account
    }

    public struct KeychainError: Error, CustomStringConvertible {
        public let status: OSStatus
        public var description: String {
            (SecCopyErrorMessageString(status, nil) as String?) ?? "Keychain error \(status)"
        }
    }

    private var query: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: service,
         kSecAttrAccount as String: account]
    }

    public func token() -> String? {
        var q = query
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var out: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let data = out as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    public func setToken(_ token: String?) throws {
        let deleted = SecItemDelete(query as CFDictionary)
        guard deleted == errSecSuccess || deleted == errSecItemNotFound else { throw KeychainError(status: deleted) }
        guard let token else { return }
        var q = query
        q[kSecValueData as String] = Data(token.utf8)
        q[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        let added = SecItemAdd(q as CFDictionary, nil)
        guard added == errSecSuccess else { throw KeychainError(status: added) }
    }
}

/// A store in memory, for tests and previews.
public final class MemoryTokenStore: TokenStore {
    private let value: Mutex<String?>

    public init(_ token: String? = nil) { value = Mutex(token) }

    public func token() -> String? { value.withLock { $0 } }
    public func setToken(_ token: String?) throws { value.withLock { $0 = token } }
}
