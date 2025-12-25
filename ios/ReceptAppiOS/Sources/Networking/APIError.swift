import Foundation

enum APIError: Error {
    case invalidURL
    case invalidResponse
    case httpStatus(Int)
    case decoding(Error)
    case network(Error)
}

extension APIError {
    static func userFacingMessage(for error: Error) -> String {
        if let apiError = error as? APIError {
            switch apiError {
            case .httpStatus(400):
                return "Fel användarnamn eller lösenord."
            case .httpStatus(let code):
                return "Serverfel (HTTP \(code))."
            case .invalidResponse:
                return "Ogiltigt svar från servern."
            case .invalidURL:
                return "Ogiltig API-adress."
            case .decoding:
                return "Kunde inte tolka data från servern."
            case .network:
                return "Nätverksfel."
            }
        }
        return "Ett fel inträffade."
    }
}
