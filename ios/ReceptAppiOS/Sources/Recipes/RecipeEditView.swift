import SwiftUI

@MainActor
struct RecipeEditView: View {
    @EnvironmentObject private var session: SessionController
    @Environment(\.dismiss) private var dismiss

    private let recipeId: Int
    private let initialDishType: String
    private let initialTags: String
    private let initialServings: Int?
    private let onSaved: (RecipeDTO) -> Void

    @State private var title: String
    @State private var description: String
    @State private var ingredients: String
    @State private var steps: String
    @State private var cookingTimeMinutesText: String
    @State private var servingsText: String
    @State private var dishType: String
    @State private var tags: String

    @State private var isSaving = false
    @State private var errorMessage: String? = nil

    init(recipe: RecipeDTO, onSaved: @escaping (RecipeDTO) -> Void) {
        self.recipeId = recipe.id
        self.initialDishType = recipe.dishType ?? "lunch_dinner"
        self.onSaved = onSaved
        self.initialTags = recipe.tags ?? ""
        self.initialServings = recipe.servings

        _title = State(initialValue: recipe.title)
        _description = State(initialValue: recipe.description ?? "")
        _ingredients = State(initialValue: recipe.ingredients ?? "")
        _steps = State(initialValue: recipe.steps ?? "")
        _cookingTimeMinutesText = State(initialValue: (recipe.cookingTime.map(String.init) ?? ""))
        _servingsText = State(initialValue: (recipe.servings.map(String.init) ?? ""))
        _dishType = State(initialValue: recipe.dishType ?? "lunch_dinner")
        _tags = State(initialValue: recipe.tags ?? "")
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Grund") {
                    TextField("Titel", text: $title)
                        .textInputAutocapitalization(.sentences)

                    Picker("Kategori", selection: $dishType) {
                        ForEach(RecipeDTO.allDishTypes, id: \.id) { type in
                            Text(type.name).tag(type.id)
                        }
                    }

                    TextField("Tid (minuter)", text: $cookingTimeMinutesText)
                        .keyboardType(.numberPad)

                    TextField("Portioner", text: $servingsText)
                        .keyboardType(.numberPad)

                    TextField("Taggar (kommaseparerade)", text: $tags)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled(true)
                    Text("Ex: middag, snabbt, vegetariskt")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    Button("Föreslå taggar") {
                        tags = mergeSuggestedTags(into: tags)
                    }
                }

                Section("Beskrivning") {
                    TextEditor(text: $description)
                        .frame(minHeight: 90)
                }

                Section("Ingredienser") {
                    Text("En ingrediens per rad är enklast.")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    TextEditor(text: $ingredients)
                        .frame(minHeight: 140)
                }

                Section("Gör så här") {
                    Text("Ett steg per rad är enklast.")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    TextEditor(text: $steps)
                        .frame(minHeight: 160)
                }

            }
            .navigationTitle("Redigera")
            .navigationBarTitleDisplayMode(.inline)
            .safeAreaInset(edge: .bottom) {
                if let errorMessage {
                    Text(errorMessage)
                        .frame(maxWidth: .infinity)
                        .padding(12)
                        .background(.thinMaterial)
                }
            }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Avbryt") { dismiss() }
                        .disabled(isSaving)
                }

                ToolbarItem(placement: .confirmationAction) {
                    Button {
                        Task { await save() }
                    } label: {
                        if isSaving {
                            ProgressView()
                        } else {
                            Text("Spara")
                        }
                    }
                    .disabled(isSaving || title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
        }
    }

    private func save() async {
        guard let token = session.token else { return }
        isSaving = true
        errorMessage = nil
        defer { isSaving = false }

        var fields: [String: Any] = [:]

        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        fields["title"] = trimmedTitle

        let trimmedDescription = description.trimmingCharacters(in: .whitespacesAndNewlines)
        fields["description"] = trimmedDescription

        fields["ingredients"] = ingredients.trimmingCharacters(in: .whitespacesAndNewlines)
        fields["steps"] = steps.trimmingCharacters(in: .whitespacesAndNewlines)

        let timeTrimmed = cookingTimeMinutesText.trimmingCharacters(in: .whitespacesAndNewlines)
        if timeTrimmed.isEmpty {
            // If user clears it, set to null/empty? We'll just omit so it stays unchanged.
        } else if let minutes = Int(timeTrimmed), minutes >= 0 {
            fields["cooking_time"] = minutes
        } else {
            errorMessage = "Tid måste vara ett heltal i minuter."
            return
        }

        let servingsTrimmed = servingsText.trimmingCharacters(in: .whitespacesAndNewlines)
        if servingsTrimmed.isEmpty {
            // Omit => unchanged.
        } else if let servings = Int(servingsTrimmed), servings > 0 {
            if initialServings != servings {
                fields["servings"] = servings
            }
        } else {
            errorMessage = "Portioner måste vara ett heltal."
            return
        }

        if dishType != initialDishType {
            fields["dish_type"] = dishType
        } else {
            // still allow explicitly setting, but safe to omit.
        }

        let normalizedTags = normalizeTags(tags)
        let normalizedInitialTags = normalizeTags(initialTags)
        if normalizedTags != normalizedInitialTags {
            fields["tags"] = normalizedTags
        }

        do {
            let updated = try await APIClient.shared.updateRecipe(id: recipeId, fields: fields, token: token)
            onSaved(updated)
            dismiss()
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }

    private func mergeSuggestedTags(into current: String) -> String {
        let existing = normalizeTags(current)
            .split(separator: ",")
            .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        let text = "\(title) \(ingredients) \(steps)".lowercased()
        let suggestions = suggestTags(in: text)

        var combined: [String] = []
        var seen = Set<String>()
        for tag in existing + suggestions {
            let cleaned = tag.trimmingCharacters(in: .whitespacesAndNewlines)
                .trimmingCharacters(in: CharacterSet(charactersIn: "#"))
            guard !cleaned.isEmpty else { continue }
            if !seen.contains(cleaned) {
                seen.insert(cleaned)
                combined.append(cleaned)
            }
        }

        return combined.joined(separator: ", ")
    }

    private func suggestTags(in lowercasedText: String) -> [String] {
        let keywords: [(String, String)] = [
            ("kyckling", "kyckling"),
            ("lax", "fisk"),
            ("torsk", "fisk"),
            ("räkor", "skaldjur"),
            ("pasta", "pasta"),
            ("korv", "korv"),
            ("soppa", "soppa"),
            ("färs", "färs"),
            ("kött", "kött"),
            ("tofu", "vegetariskt"),
            ("linser", "vegetariskt"),
            ("bönor", "vegetariskt"),
            ("choklad", "dessert"),
            ("bakpulver", "dessert")
        ]

        var out: [String] = []
        for (needle, tag) in keywords {
            if lowercasedText.contains(needle) {
                out.append(tag)
            }
        }

        var seen = Set<String>()
        return out.filter { seen.insert($0).inserted }
    }

    private func normalizeTags(_ input: String) -> String {
        let raw = input
            .split(separator: ",")
            .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        var seen: Set<String> = []
        var out: [String] = []
        for tag in raw {
            let key = tag.lowercased()
            if seen.contains(key) { continue }
            seen.insert(key)
            out.append(tag)
        }
        return out.joined(separator: ", ")
    }
}

