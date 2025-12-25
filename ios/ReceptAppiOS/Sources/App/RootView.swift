import SwiftUI

struct RootView: View {
    @EnvironmentObject private var session: SessionController

    var body: some View {
        Group {
            if session.isAuthenticated {
                RecipeListView()
            } else {
                LoginView()
            }
        }
        .task {
            session.loadFromStorageIfNeeded()
        }
    }
}
