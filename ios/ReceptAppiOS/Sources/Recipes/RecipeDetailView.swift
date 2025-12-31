import SwiftUI

struct RecipeDetailView: View {
    @EnvironmentObject private var session: SessionController

    @State private var recipe: RecipeDTO
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil
    @State private var showSuccessAlert = false
    @State private var showEditSheet = false

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

            if let url = recipe.preferredImageURL {
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

            Section {
                Picker("Kategori", selection: Binding(
                    get: { recipe.dishType ?? "lunch_dinner" },
                    set: { newValue in
                        Task { await updateDishType(newValue) }
                    }
                )) {
                    ForEach(RecipeDTO.allDishTypes, id: \.id) { type in
                        Text(type.name).tag(type.id)
                    }
                }
                
                if let minutes = recipe.cookingTime, minutes > 0 {
                    HStack {
                        Text("Tid")
                        Spacer()
                        Text(formatDuration(minutes))
                            .foregroundStyle(.secondary)
                    }
                }
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
                        Task { await addToShoppingList() }
                    }
                    .disabled(isLoading)
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
            ToolbarItem(placement: .topBarTrailing) {
                Button("Redigera") { showEditSheet = true }
                    .disabled(isLoading)
            }

            if isLoading {
                ToolbarItem(placement: .topBarTrailing) {
                    ProgressView()
                }
            }
        }
        .sheet(isPresented: $showEditSheet) {
            RecipeEditView(recipe: recipe) { updated in
                // Update local detail + ask list views to refresh.
                recipe = updated
                session.reloadRecipesSignal += 1
            }
            .environmentObject(session)
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
        .alert("Tillagt", isPresented: $showSuccessAlert) {
            Button("OK", role: .cancel) { }
        } message: {
            Text("Ingredienserna har lagts till i din inköpslista.")
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

    private func formatDuration(_ minutes: Int) -> String {
        if minutes < 60 {
            return "\(minutes) min"
        }
        let h = minutes / 60
        let m = minutes % 60
        if m == 0 {
            return "\(h) tim"
        }
        return "\(h) tim \(m) min"
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

    private func addToShoppingList() async {
        guard let token = session.token else { return }
        isLoading = true
        defer { isLoading = false }
        
        do {
            try await APIClient.shared.addIngredientsToShoppingList(recipeId: recipe.id, shoppingListId: nil, token: token)
            showSuccessAlert = true
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }

    private func updateDishType(_ newType: String) async {
        guard let token = session.token else { return }
        // Don't set isLoading = true here as it might block the UI too much for a simple picker change
        // or we can use a separate loading state if needed.
        // For now, let's just do it.
        
        do {
            let updatedRecipe = try await APIClient.shared.updateRecipe(
                id: recipe.id,
                fields: ["dish_type": newType],
                token: token
            )
            recipe = updatedRecipe
            session.reloadRecipesSignal += 1
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }
}
