import Foundation

enum AppConfig {
    static var apiBaseURL: URL {
        guard
            let raw = Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL") as? String,
            let url = URL(string: raw)
        else {
            return URL(string: "http://127.0.0.1:8000/api/")!
        }
        return url
    }
}
