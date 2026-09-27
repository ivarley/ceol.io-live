// A session_instance_tune id as the logger holds it: the server's integer once a row
// has settled, or "temp-<op_id>" for an optimistic row the server hasn't answered
// yet. The web keeps both in one JS value; Swift needs to say which.

public enum RecordID: Hashable, Sendable {
    case server(Int)
    case temp(String)

    /// From a JSON value: an integral number is a server id, a string a temp id.
    public init?(_ value: JSONValue?) {
        switch value {
        case .number?:
            guard let n = value?.intValue else { return nil }
            self = .server(n)
        case .string(let s)?:
            self = .temp(s)
        default:
            return nil
        }
    }

    public var json: JSONValue {
        switch self {
        case .server(let n): return JSONValue(n)
        case .temp(let s): return .string(s)
        }
    }

    /// `typeof v === 'string' && v.startsWith('temp-')`
    public var isTempString: Bool {
        if case .temp(let s) = self { return s.hasPrefix("temp-") }
        return false
    }
}
