import SwiftUI

struct CookbookRecipesView: View {
    @EnvironmentObject private var session: SessionController

    let cookbook: CookbookDTO

    @State private var recipes: [RecipeDTO] = []
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil

    var body: some View {
        List {
            if recipes.isEmpty {
                Section {
                    Text(isLoading ? "Laddar..." : "Inga recept i kokboken än")
                        .foregroundStyle(.secondary)
                }
            } else {
                Section {
                    ForEach(recipes.sorted { $0.title.localizedCaseInsensitiveCompare($1.title) == .orderedAscending }) { recipe in
                        NavigationLink(value: recipe) {
                            Text(recipe.title)
                                .foregroundStyle(.primary)
                                .lineLimit(2)
                        }
                    }
                }
            }
        }
        .navigationTitle(cookbook.name)
        .navigationBarTitleDisplayMode(.inline)
        .listStyle(.insetGrouped)
        .overlay {
            if isLoading && recipes.isEmpty {
                ProgressView("Laddar recept...")
            }
        }
        .safeAreaInset(edge: .bottom) {
            if let errorMessage {
                Text(errorMessage)
                    .frame(maxWidth: .infinity)
                    .padding(12)
                    .background(.thinMaterial)
            }
        }
        .task {
            await loadCookbookRecipes()
        }
        .refreshable {
            await loadCookbookRecipes()
        }
    }

    @MainActor
    private func loadCookbookRecipes() async {
        guard let token = session.token else { return }
        guard !isLoading else { return }

        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            recipes = try await APIClient.shared.fetchCookbookRecipes(cookbookId: cookbook.id, token: token)
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }
}
