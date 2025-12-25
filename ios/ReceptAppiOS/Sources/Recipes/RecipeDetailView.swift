import SwiftUI

struct RecipeDetailView: View {
    @EnvironmentObject private var session: SessionController

    @State private var recipe: RecipeDTO
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil
    @State private var showShoppingListSheet = false
    @State private var shoppingLists: [ShoppingListDTO] = []

    init(recipe: RecipeDTO) {
        _recipe = State(initialValue: recipe)
    }

    var body: some View {
        List {
            let steps = parseSteps(recipe.steps)

            if !steps.isEmpty {
                Section {
                    NavigationLink("Starta Cook Mode") {
                        CookModeView(title: recipe.title, steps: steps)
                    }
                }
            }

            if let url = recipe.imageURL {
                Section {
                    AsyncImage(url: url) { image in
                        image
                            .resizable()
                            .scaledToFill()
                    } placeholder: {
                        ProgressView()
                    }
                    .frame(height: 220)
                    .clipped()
                }
                .listRowInsets(EdgeInsets())
            }

            if let description = recipe.description, !description.isEmpty {
                Section("Beskrivning") {
                    Text(description)
                }
            }

            let ingredients = IngredientsParser.parse(recipe.ingredients)
            if !ingredients.isEmpty {
                Section("Ingredienser") {
                    ForEach(ingredients) { ing in
                        Text(formatIngredient(ing))
                    }
                    Button("Lägg till i inköpslista") {
                        showShoppingListSheet = true
                    }
                }
            }

            if !steps.isEmpty {
                Section("Gör så här") {
                    ForEach(Array(steps.enumerated()), id: \.offset) { idx, step in
                        VStack(alignment: .leading, spacing: 6) {
                            Text("\(idx + 1).")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Text(step)
                        }
                        .padding(.vertical, 4)
                    }
                }
            }

            if (recipe.description ?? "").trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
               ingredients.isEmpty,
               steps.isEmpty {
                Section("Innehåll") {
                    Text("Det här receptet saknar ingredienser eller steg.")
                        .foregroundStyle(.secondary)
                }
            }
        }
        .navigationTitle(recipe.title)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if isLoading {
                ToolbarItem(placement: .topBarTrailing) {
                    ProgressView()
                }
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
            await loadRecipe()
        }
        .confirmationDialog("Välj inköpslista", isPresented: $showShoppingListSheet) {
            ForEach(shoppingLists) { list in
                Button(list.name) {
                    Task { await addToShoppingList(listId: list.id) }
                }
            }
            Button("Avbryt", role: .cancel) {}
        }
        .refreshable {
            await loadRecipe()
        }
    }

    private func formatIngredient(_ ing: IngredientDTO) -> String {
        let parts = [ing.amount, ing.unit, ing.name]
            .compactMap { $0?.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        return parts.joined(separator: " ")
    }

    private func parseSteps(_ raw: String?) -> [String] {
        let normalized = (raw ?? "")
            .replacingOccurrences(of: "\r\n", with: "\n")
            .replacingOccurrences(of: "\r", with: "\n")

        let byLines = normalized
            .split(separator: "\n")
            .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        if byLines.count > 1 {
            return byLines
        }

        var bySentences: [String] = []
        normalized.enumerateSubstrings(in: normalized.startIndex..<normalized.endIndex, options: [.bySentences]) { substring, _, _, _ in
            if let substring {
                let trimmed = substring.trimmingCharacters(in: .whitespacesAndNewlines)
                if !trimmed.isEmpty {
                    bySentences.append(trimmed)
                }
            }
        }

        if bySentences.count > 1 {
            return bySentences
        }

        return byLines
    }
async let recipeTask = APIClient.shared.fetchRecipe(id: recipe.id, token: token)
            async let listsTask = APIClient.shared.fetchShoppingLists(token: token)
            
            let (fetchedRecipe, fetchedLists) = try await (recipeTask, listsTask)
            recipe = fetchedRecipe
            shoppingLists = fetchedLists
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }

    private func addToShoppingList(listId: Int) async {
        guard let token = session.token else { return }
        isLoading = true
        defer { isLoading = false }
        
        do {
            try await APIClient.shared.addIngredientsToShoppingList(recipeId: recipe.id, shoppingListId: listI
    private func loadRecipe() async {
        guard let token = session.token else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            recipe = try await APIClient.shared.fetchRecipe(id: recipe.id, token: token)
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }
}
