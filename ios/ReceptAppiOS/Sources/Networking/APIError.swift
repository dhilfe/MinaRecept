import Foundation

enum APIError: Error {
    case invalidURL
    case invalidResponse
    case httpStatus(Int, String?)
    case decoding(Error)
    case network(Error)
}

extension APIError {
    static func userFacingMessage(for error: Error) -> String {
        if let apiError = error as? APIError {
            switch apiError {
            case .httpStatus(400, let message):
                return message ?? "Ogiltig förfrågan. Kontrollera att alla fält är korrekt ifyllda."
            case .httpStatus(401, _):
                return "Fel användarnamn eller lösenord."
            case .httpStatus(let code, let message):
                return message ?? "Serverfel (HTTP \(code))."
            case .invalidResponse:
                return "Ogiltigt svar från servern."
            case .invalidURL:
                return "Ogiltig API-adress."
            case .decoding:
                return "Kunde inte tolka data från servern."
            case .network(let underlying):
                if let urlError = underlying as? URLError {
                    switch urlError.code {
                    case .appTransportSecurityRequiresSecureConnection:
                        return "Nätverksfel: HTTP blockeras av iOS (ATS)."
                    case .cannotConnectToHost:
                        return "Nätverksfel: kan inte ansluta till servern."
                    case .cannotFindHost:
                        return "Nätverksfel: hittar inte servern."
                    case .timedOut:
                        return "Nätverksfel: timeout mot servern."
                    case .notConnectedToInternet:
                        return "Nätverksfel: ingen internetanslutning."
                    default:
                        return "Nätverksfel (\(urlError.code.rawValue))."
                    }
                }
                return "Nätverksfel."
            }
        }
        return "Ett fel inträffade."
    }
}
