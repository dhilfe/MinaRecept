import Foundation

enum AppConfig {
    static var apiBaseURL: URL {
        guard
            let raw = Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL") as? String,
            let url = URL(string: raw)
        else {
            return URL(string: "http://localhost:8000/api/")!
        }
        return url
    }
}
