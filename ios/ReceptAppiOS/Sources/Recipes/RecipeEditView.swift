import SwiftUI

@MainActor
struct RecipeEditView: View {
    @EnvironmentObject private var session: SessionController
    @Environment(\.dismiss) private var dismiss

    private let recipeId: Int
    private let initialDishType: String
        private let initialTags: String
    private let onSaved: (RecipeDTO) -> Void

    @State private var title: String
    @State private var description: String
    @State private var ingredients: String
    @State private var steps: String
    @State private var cookingTimeMinutesText: String
    @State private var dishType: String
        @State private var tags: String

    @State private var isSaving = false
    @State private var errorMessage: String? = nil

    init(recipe: RecipeDTO, onSaved: @escaping (RecipeDTO) -> Void) {
        self.recipeId = recipe.id
        self.initialDishType = recipe.dishType ?? "lunch_dinner"
        self.onSaved = onSaved
            self.initialTags = recipe.tags ?? ""

        _title = State(initialValue: recipe.title)
        _description = State(initialValue: recipe.description ?? "")
        _ingredients = State(initialValue: recipe.ingredients ?? "")
        _steps = State(initialValue: recipe.steps ?? "")
        _cookingTimeMinutesText = State(initialValue: (recipe.cookingTime.map(String.init) ?? ""))
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

                        TextField("Taggar (kommaseparerade)", text: $tags)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled(true)
                        Text("Ex: middag, snabbt, vegetariskt")
                            .font(.caption)
                            .foregroundStyle(.secondary)
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

                if let errorMessage {
                    Section {
                        Text(errorMessage)
                            .foregroundStyle(.red)
                    }
                }
            }
            .navigationTitle("Redigera")
            .navigationBarTitleDisplayMode(.inline)
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

