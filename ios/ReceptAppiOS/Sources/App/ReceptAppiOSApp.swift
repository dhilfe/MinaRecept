import SwiftUI
import os

private let deepLinkLogger = Logger(subsystem: "se.receptapp.ios", category: "DeepLink")

@main
struct ReceptAppiOSApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var session = SessionController()
    @StateObject private var deepLinkStore = DeepLinkStore.shared

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(session)
                .preferredColorScheme(.light)
                .onReceive(deepLinkStore.$pendingURL) { url in
                    guard let url else { return }
                    // Consume first to avoid duplicate handling.
                    _ = deepLinkStore.consumePendingURL()
                    deepLinkLogger.info("received pendingURL: \(url.absoluteString, privacy: .public)")
                    session.handleIncomingURL(url)
                }
                .onOpenURL { url in
                    deepLinkLogger.info("onOpenURL: \(url.absoluteString, privacy: .public)")
                    session.handleIncomingURL(url)
                }
        }
    }
}
