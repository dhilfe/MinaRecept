import SwiftUI

struct CookbookRecipesView: View {
    @EnvironmentObject private var session: SessionController

    let cookbook: CookbookDTO

    @State private var recipes: [RecipeDTO] = []
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil

    private struct RecipeRow: View {
        let recipe: RecipeDTO

        var body: some View {
            HStack(alignment: .top, spacing: 12) {
                if let url = recipe.preferredImageURL {
                    AsyncImage(url: url) { image in
                        image
                            .resizable()
                            .scaledToFill()
                    } placeholder: {
                        RoundedRectangle(cornerRadius: 12)
                            .fill(Color.secondary.opacity(0.15))
                    }
                    .frame(width: 64, height: 64)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .overlay {
                        RoundedRectangle(cornerRadius: 12)
                            .strokeBorder(.secondary.opacity(0.15))
                    }
                } else {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color.secondary.opacity(0.10))
                        .frame(width: 64, height: 64)
                        .overlay {
                            Image(systemName: "fork.knife")
                                .foregroundStyle(.secondary)
                        }
                }

                VStack(alignment: .leading, spacing: 6) {
                    Text(recipe.title)
                        .font(.headline)
                        .foregroundStyle(.primary)
                        .lineLimit(2)
                }

                Spacer(minLength: 0)
            }
            .padding(.vertical, 2)
        }
    }

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
                            RecipeRow(recipe: recipe)
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
