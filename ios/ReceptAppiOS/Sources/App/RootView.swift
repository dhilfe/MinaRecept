import SwiftUI

struct RootView: View {
    @EnvironmentObject private var session: SessionController

    @State private var showWelcome = !UserDefaults.standard.bool(forKey: "hasSeenWelcomeScreen")

    var body: some View {
        Group {
            if showWelcome {
                WelcomeView {
                    UserDefaults.standard.set(true, forKey: "hasSeenWelcomeScreen")
                    showWelcome = false
                }
            } else if session.isAuthenticated {
                MainTabView()
            } else {
                LoginView()
            }
        }
        .task {
            session.loadFromStorageIfNeeded()
        }
    }
}
