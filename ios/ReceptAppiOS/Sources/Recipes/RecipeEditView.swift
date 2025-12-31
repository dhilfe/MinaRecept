import SwiftUI

@MainActor
struct RecipeEditView: View {
    @EnvironmentObject private var session: SessionController
    @Environment(\.dismiss) private var dismiss

    private let recipeId: Int
    private let initialDishType: String
    private let onSaved: (RecipeDTO) -> Void

    @State private var title: String
    @State private var description: String
    @State private var ingredients: String
    @State private var steps: String
    @State private var cookingTimeMinutesText: String
    @State private var dishType: String

    @State private var isSaving = false
    @State private var errorMessage: String? = nil

    init(recipe: RecipeDTO, onSaved: @escaping (RecipeDTO) -> Void) {
        self.recipeId = recipe.id
        self.initialDishType = recipe.dishType ?? "lunch_dinner"
        self.onSaved = onSaved

        _title = State(initialValue: recipe.title)
        _description = State(initialValue: recipe.description ?? "")
        _ingredients = State(initialValue: recipe.ingredients ?? "")
        _steps = State(initialValue: recipe.steps ?? "")
        _cookingTimeMinutesText = State(initialValue: (recipe.cookingTime.map(String.init) ?? ""))
        _dishType = State(initialValue: recipe.dishType ?? "lunch_dinner")
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

        do {
            let updated = try await APIClient.shared.updateRecipe(id: recipeId, fields: fields, token: token)
            onSaved(updated)
            dismiss()
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }
}

import SwiftUI

struct RecipeEditView: View {
    @EnvironmentObject private var session: SessionController
    @Environment(\.dismiss) private var dismiss

    let recipe: RecipeDTO
    // Closure to update parent view with new data
    let onSave: (RecipeDTO) -> Void

    @State private var title: String
    @State private var description: String
    @State private var cookingTimeMinutes: Int
    @State private var servings: Int
    @State private var ingredients: [String]
    @State private var instructions: [String]
    
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil

    init(recipe: RecipeDTO, onSave: @escaping (RecipeDTO) -> Void) {
        self.recipe = recipe
        self.onSave = onSave
        _title = State(initialValue: recipe.title)
        _description = State(initialValue: recipe.description)
        _cookingTimeMinutes = State(initialValue: recipe.cookingTimeMinutes)
        _servings = State(initialValue: recipe.servings)
        _ingredients = State(initialValue: recipe.ingredients)
        _instructions = State(initialValue: recipe.instructions)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Information") {
                    TextField("Titel", text: $title)
                    TextField("Beskrivning", text: $description, axis: .vertical)
                        .lineLimit(3...6)
                }

                Section("Tid & Portioner") {
                    HStack {
                        Text("Tid (min)")
                        Spacer()
                        TextField("Minuter", value: $cookingTimeMinutes, format: .number)
                            .keyboardType(.numberPad)
                            .multilineTextAlignment(.trailing)
                            .frame(width: 80)
                    }
                    HStack {
                        Text("Portioner")
                        Spacer()
                        Stepper("\(servings)", value: $servings, in: 1...100)
                    }
                }

                Section("Ingredienser") {
                    ForEach($ingredients.indices, id: \.self) { index in
                        TextField("Ingrediens", text: $ingredients[index])
                    }
                    .onDelete { offsets in
                        ingredients.remove(atOffsets: offsets)
                    }
                    
                    Button("Lägg till ingrediens") {
                        ingredients.append("")
                    }
                }

                Section("Instruktioner") {
                    ForEach($instructions.indices, id: \.self) { index in
                        HStack(alignment: .top) {
                            Text("\(index + 1).")
                                .foregroundStyle(.secondary)
                                .padding(.top, 8)
                            TextField("Instruktion", text: $instructions[index], axis: .vertical)
                        }
                    }
                    .onDelete { offsets in
                        instructions.remove(atOffsets: offsets)
                    }
                    .onMove { from, to in
                        instructions.move(fromOffsets: from, toOffset: to)
                    }

                    Button("Lägg till steg") {
                        instructions.append("")
                    }
                }
            }
            .navigationTitle("Redigera recept")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Avbryt") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Spara") {
                        save()
                    }
                    .disabled(title.isEmpty || isLoading)
                }
            }
            .overlay {
                if isLoading {
                    ProgressView()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .background(.black.opacity(0.2))
                }
            }
            .alert("Fel", isPresented: Binding(get: { errorMessage != nil }, set: { if !$0 { errorMessage = nil } })) {
                Button("OK", role: .cancel) { }
            } message: {
                if let errorMessage {
                    Text(errorMessage)
                }
            }
        }
    }

    private func save() {
        guard let token = session.token else { return }
        isLoading = true
        errorMessage = nil

        // Filter out empty lines
        let cleanIngredients = ingredients.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }
        let cleanInstructions = instructions.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }

        let fields: [String: Any] = [
            "title": title,
            "description": description,
            "cooking_time_minutes": cookingTimeMinutes,
            "servings": servings,
            "ingredients": cleanIngredients,
            "instructions": cleanInstructions
        ]

        Task {
            do {
                let updated = try await APIClient.shared.updateRecipe(id: recipe.id, fields: fields, token: token)
                onSave(updated)
                dismiss()
            } catch {
                errorMessage = APIError.userFacingMessage(for: error)
            }
            isLoading = false
        }
    }
}

