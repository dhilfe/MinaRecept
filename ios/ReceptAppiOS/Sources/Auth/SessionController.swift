import Foundation

@MainActor
final class SessionController: ObservableObject {
    @Published private(set) var token: String? = nil

    private let tokenStore: TokenStoring

    init(tokenStore: TokenStoring = KeychainTokenStore()) {
        self.tokenStore = tokenStore
    }

    var isAuthenticated: Bool {
        token != nil
    }

    func loadFromStorageIfNeeded() {
        if token == nil {
            token = tokenStore.loadToken()
        }
    }

    func setToken(_ token: String) {
        self.token = token
        tokenStore.saveToken(token)
    }

    func logout() {
        token = nil
        tokenStore.clearToken()
    }
}
