import SwiftUI

struct RootView: View {
    @EnvironmentObject private var session: SessionController

    var body: some View {
        Group {
            if session.isAuthenticated {
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
