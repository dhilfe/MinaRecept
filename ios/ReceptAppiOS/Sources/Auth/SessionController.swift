import Foundation
import os

private let sessionLogger = Logger(subsystem: "se.receptapp.ios", category: "Session")

private enum AppGroupConfig {
    static let suiteName = "group.se.enklagrejer.minarecept"
    static let tokenKey = "auth_token"
}

@MainActor
final class SessionController: ObservableObject {
    @Published private(set) var token: String? = nil
    @Published private(set) var reloadRecipesSignal: Int = 0

    private var pendingImportURLString: String? = nil

    private let tokenStore: TokenStoring

    init(tokenStore: TokenStoring = KeychainTokenStore()) {
        self.tokenStore = tokenStore
    }

    var isAuthenticated: Bool {
        token != nil
    }

    func triggerReloadRecipes() {
        reloadRecipesSignal += 1
    }

    func loadFromStorageIfNeeded() {
        if token == nil {
            token = tokenStore.loadToken()
            
            // Ensure token is synced to App Group (in case it was lost or only in Keychain)
            if let token {
                let sharedDefaults = UserDefaults(suiteName: AppGroupConfig.suiteName)
                sharedDefaults?.set(token, forKey: AppGroupConfig.tokenKey)
            }
        }
        processPendingImportIfPossible()
    }

    func setToken(_ token: String) {
        self.token = token
        tokenStore.saveToken(token)

        // Share token with the Share Extension via App Group UserDefaults.
        // NOTE: Requires App Groups entitlements for both targets.
        let sharedDefaults = UserDefaults(suiteName: AppGroupConfig.suiteName)
        sharedDefaults?.set(token, forKey: AppGroupConfig.tokenKey)
        sharedDefaults?.synchronize()
        if let writtenToken = sharedDefaults?.string(forKey: AppGroupConfig.tokenKey) {
            sessionLogger.info("[DEBUG] Token written to App Group: \(writtenToken, privacy: .private)")
        } else {
            sessionLogger.error("[DEBUG] Failed to write token to App Group UserDefaults!")
        }
        processPendingImportIfPossible()
    }

    func logout() {
        token = nil
        tokenStore.clearToken()

        // Clear shared token.
        UserDefaults(suiteName: AppGroupConfig.suiteName)?.removeObject(forKey: AppGroupConfig.tokenKey)
    }

    func handleIncomingURL(_ url: URL) {
        sessionLogger.info("handleIncomingURL: \(url.absoluteString, privacy: .public)")

        guard url.scheme == "receptapp" else {
            sessionLogger.debug("Ignoring URL with non-matching scheme")
            return
        }

        // Expected: receptapp://import?url=<sharedUrl>
        // Also accept: receptapp:///import?url=<sharedUrl>
        let isImportLink = (url.host == "import") || (url.host == nil && url.path == "/import")
        guard isImportLink else {
            sessionLogger.debug("Ignoring receptapp URL (not import): host=\(url.host ?? "(nil)", privacy: .public) path=\(url.path, privacy: .public)")
            return
        }
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
            sessionLogger.error("Failed to parse URLComponents")
            return
        }
        let sharedURLString = components.queryItems?.first(where: { $0.name == "url" })?.value
        guard let sharedURLString, !sharedURLString.isEmpty else {
            sessionLogger.error("Missing url query parameter")
            return
        }

        sessionLogger.info("Received shared URL: \(sharedURLString, privacy: .public)")

        pendingImportURLString = sharedURLString
        loadFromStorageIfNeeded()
        processPendingImportIfPossible()
    }

    private func processPendingImportIfPossible() {
        guard let token else {
            if pendingImportURLString != nil {
                sessionLogger.info("Deferring import until token is available")
            }
            return
        }
        guard let pendingImportURLString else { return }

        sessionLogger.info("Starting import for pending URL")

        // Clear immediately to avoid repeated imports if the request is slow.
        self.pendingImportURLString = nil

        Task {
            do {
                try await APIClient.shared.importRecipe(url: pendingImportURLString, token: token)
                sessionLogger.info("Import succeeded")
                await MainActor.run { self.triggerReloadRecipes() }
            } catch {
                sessionLogger.error("Import failed: \(String(describing: error), privacy: .public)")
                // If needed later, we can surface an alert; for now rely on existing views.
                // Restore pending URL so user can retry by re-sharing.
            }
        }
    }
}
