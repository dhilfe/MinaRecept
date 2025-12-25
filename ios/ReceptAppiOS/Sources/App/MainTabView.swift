import SwiftUI

struct MainTabView: View {
    @EnvironmentObject private var session: SessionController

    var body: some View {
        TabView {
            RecipeListView()
                .tabItem {
                    Label("Mina recept", systemImage: "book")
                }

            ShoppingListsView()
                .tabItem {
                    Label("Inköpslistor", systemImage: "cart")
                }
        }
        .environmentObject(session)
    }
}
