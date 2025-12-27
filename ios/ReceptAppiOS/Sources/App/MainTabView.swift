import SwiftUI

struct MainTabView: View {
    @EnvironmentObject private var session: SessionController

    private enum Tab: Int {
        case recipes = 0
        case weeklyPlan = 1
        case shoppingLists = 2
    }

    @State private var selectedTab: Tab = .recipes
    @State private var recipesResetToken: Int = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            RecipeListView(resetToken: recipesResetToken)
                .tabItem {
                    Label("Mina recept", systemImage: "book")
                }
                .tag(Tab.recipes)

            WeeklyPlanView()
                .tabItem {
                    Label("Veckoplan", systemImage: "calendar")
                }
                .tag(Tab.weeklyPlan)

            ShoppingListsView()
                .tabItem {
                    Label("Inköpslistor", systemImage: "cart")
                }
                .tag(Tab.shoppingLists)
        }
        .environmentObject(session)
        .onChange(of: selectedTab) { newValue in
            // Treat selecting "Mina recept" as a home action.
            if newValue == .recipes {
                recipesResetToken &+= 1
            }
        }
    }
}
