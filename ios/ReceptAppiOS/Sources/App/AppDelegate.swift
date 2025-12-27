import UIKit
import os

private let deepLinkLogger = Logger(subsystem: "se.receptapp.ios", category: "DeepLink")

@MainActor
final class DeepLinkStore: ObservableObject {
    static let shared = DeepLinkStore()

    @Published var pendingURL: URL? = nil

    private init() {}

    func consumePendingURL() -> URL? {
        let url = pendingURL
        pendingURL = nil
        return url
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        open url: URL,
        options: [UIApplication.OpenURLOptionsKey: Any] = [:]
    ) -> Bool {
        deepLinkLogger.info("UIApplicationDelegate openURL: \(url.absoluteString, privacy: .public)")

        Task { @MainActor in
            DeepLinkStore.shared.pendingURL = url
        }

        return true
    }
}
