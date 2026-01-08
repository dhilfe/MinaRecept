import SwiftUI

@MainActor
struct RecipeCreateView: View {
    @EnvironmentObject private var session: SessionController
    @Environment(\.dismiss) private var dismiss

    let onCreated: (RecipeDTO) -> Void

    @State private var title: String = ""
    @State private var description: String = ""
    @State private var ingredients: String = ""
    @State private var steps: String = ""
    @State private var cookingTimeMinutesText: String = "30"
    @State private var servingsText: String = "4"
    @State private var dishType: String = "lunch_dinner"
    @State private var tags: String = ""

    @State private var isSaving = false
    @State private var errorMessage: String? = nil

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
            .navigationTitle("Nytt recept")
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

        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedIngredients = ingredients.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedSteps = steps.trimmingCharacters(in: .whitespacesAndNewlines)

        if trimmedIngredients.isEmpty {
            errorMessage = "Ingredienser kan inte vara tomt."
            return
        }
        if trimmedSteps.isEmpty {
            errorMessage = "Gör så här kan inte vara tomt."
            return
        }

        let timeTrimmed = cookingTimeMinutesText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let minutes = Int(timeTrimmed), minutes > 0 else {
            errorMessage = "Tid måste vara ett heltal i minuter."
            return
        }

        let servingsTrimmed = servingsText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let servings = Int(servingsTrimmed), servings > 0 else {
            errorMessage = "Portioner måste vara ett heltal."
            return
        }

        do {
            let created = try await APIClient.shared.createRecipe(
                title: trimmedTitle,
                description: description.trimmingCharacters(in: .whitespacesAndNewlines),
                ingredients: trimmedIngredients,
                steps: trimmedSteps,
                cookingTime: minutes,
                servings: servings,
                dishType: dishType,
                tags: normalizeTags(tags),
                token: token
            )
            onCreated(created)
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
