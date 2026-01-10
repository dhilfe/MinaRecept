import SwiftUI

struct CookbookRecipesView: View {
    @EnvironmentObject private var session: SessionController

    let cookbook: CookbookDTO

    @State private var recipes: [RecipeDTO] = []
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil

    @State private var showAddRecipeSheet: Bool = false
    @State private var isAddingRecipe: Bool = false

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
            Section {
                Button {
                    showAddRecipeSheet = true
                } label: {
                    Label("Lägg till recept", systemImage: "plus")
                }
                .disabled(isAddingRecipe)
            }

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
        .toolbar {
            if isAddingRecipe {
                ToolbarItem(placement: .topBarLeading) {
                    ProgressView()
                }
            }
        }
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
        .sheet(isPresented: $showAddRecipeSheet) {
            RecipeMultiPickerView { selected in
                let ids = selected.map { $0.id }
                Task { await addRecipes(recipeIds: ids) }
            }
            .environmentObject(session)
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

    @MainActor
    private func addRecipes(recipeIds: [Int]) async {
        guard let token = session.token else { return }
        guard !isAddingRecipe else { return }

        let unique = Array(Set(recipeIds))
        guard !unique.isEmpty else { return }

        isAddingRecipe = true
        errorMessage = nil
        defer { isAddingRecipe = false }

        do {
            for id in unique {
                try await APIClient.shared.addRecipeToCookbook(cookbookId: cookbook.id, recipeId: id, token: token)
            }
            await loadCookbookRecipes()
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }
}
