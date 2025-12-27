import SwiftUI

struct ShoppingListDetailView: View {
    @EnvironmentObject private var session: SessionController

    let list: ShoppingListDTO

    @State private var items: [ShoppingListItemDTO] = []
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil
    
    @State private var showAddItemSheet = false
    @State private var newItemName = ""
    @State private var newItemAmount = ""
    @State private var newItemUnit = ""
    @State private var showClearConfirmation = false

    var body: some View {
        List {
            if items.isEmpty && !isLoading {
                Text("Inga rader ännu.")
                    .foregroundStyle(.secondary)
            }

            ForEach(items) { item in
                HStack(spacing: 12) {
                    Image(systemName: item.checked ? "checkmark.circle.fill" : "circle")
                        .foregroundStyle(item.checked ? .green : .secondary)
                        .onTapGesture {
                            Task { await toggleItem(item) }
                        }

                    Text(itemDescription(item))
                        .strikethrough(item.checked)
                        .foregroundStyle(item.checked ? .secondary : .primary)
                        .lineLimit(1)
                        .truncationMode(.tail)

                    Spacer()
                }
                .contentShape(Rectangle())
                .onTapGesture {
                    Task { await toggleItem(item) }
                }
            }
            .onDelete(perform: deleteItem)
        }
        .navigationTitle(list.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                HStack {
                    Menu {
                        Button {
                            Task { await uncheckAll() }
                        } label: {
                            Label("Rensa markeringar", systemImage: "arrow.counterclockwise")
                        }
                        
                        Button(role: .destructive) {
                            showClearConfirmation = true
                        } label: {
                            Label("Rensa lista", systemImage: "trash")
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                    .disabled(items.isEmpty)
                    
                    Button {
                        newItemName = ""
                        newItemAmount = ""
                        newItemUnit = ""
                        showAddItemSheet = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            
            if isLoading {
                ToolbarItem(placement: .topBarLeading) {
                    ProgressView()
                }
            }
        }
        .alert("Rensa lista", isPresented: $showClearConfirmation) {
            Button("Avbryt", role: .cancel) { }
            Button("Rensa", role: .destructive) {
                Task { await clearList() }
            }
        } message: {
            Text("Är du säker på att du vill ta bort alla rader i listan?")
        }
        .sheet(isPresented: $showAddItemSheet) {
            NavigationStack {
                Form {
                    TextField("Namn (t.ex. Mjölk)", text: $newItemName)
                    TextField("Mängd (t.ex. 1.5)", text: $newItemAmount)
                        .keyboardType(.decimalPad)
                    TextField("Enhet (t.ex. liter)", text: $newItemUnit)
                }
                .navigationTitle("Lägg till vara")
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Avbryt") { showAddItemSheet = false }
                    }
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Lägg till") {
                            Task { await addItem() }
                        }
                        .disabled(newItemName.isEmpty)
                    }
                }
            }
            .presentationDetents([.medium])
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
            await load()
        }
        .refreshable {
            await load()
        }
    }

    private func load() async {
        guard let token = session.token else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            items = try await APIClient.shared.fetchShoppingListItems(shoppingListId: list.id, token: token)
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }

    private func clearList() async {
        guard let token = session.token else { return }
        isLoading = true
        defer { isLoading = false }
        
        do {
            try await APIClient.shared.clearShoppingList(id: list.id, token: token)
            await load()
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }

    private func uncheckAll() async {
        guard let token = session.token else { return }
        isLoading = true
        defer { isLoading = false }
        
        do {
            try await APIClient.shared.uncheckAllShoppingListItems(id: list.id, token: token)
            await load()
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }

    private func addItem() async {
        guard let token = session.token else { return }
        showAddItemSheet = false
        isLoading = true
        defer { isLoading = false }
        
        do {
            _ = try await APIClient.shared.addShoppingListItem(
                shoppingListId: list.id,
                name: newItemName,
                amount: newItemAmount.isEmpty ? nil : newItemAmount,
                unit: newItemUnit.isEmpty ? nil : newItemUnit,
                token: token
            )
            await load()
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }

    private func toggleItem(_ item: ShoppingListItemDTO) async {
        guard let token = session.token else { return }
        
        // Optimistic update (visual only, since struct is immutable we can't easily update the array in place without replacing the item)
        // But we can wait for the API response which is fast.
        
        do {
            let updatedItem = try await APIClient.shared.updateShoppingListItem(id: item.id, checked: !item.checked, token: token)
            if let index = items.firstIndex(where: { $0.id == item.id }) {
                items[index] = updatedItem
            }
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }

    private func deleteItem(at offsets: IndexSet) {
        guard let token = session.token else { return }
        
        let itemsToDelete = offsets.map { items[$0] }
        items.remove(atOffsets: offsets)
        
        Task {
            for item in itemsToDelete {
                do {
                    try await APIClient.shared.deleteShoppingListItem(id: item.id, token: token)
                } catch {
                    errorMessage = APIError.userFacingMessage(for: error)
                    await load()
                }
            }
        }
    }

    private func itemDescription(_ item: ShoppingListItemDTO) -> String {
        var parts = [item.name]
        
        if let amount = item.amount, !amount.isEmpty {
            parts.append(amount)
        }
        if let unit = item.unit, !unit.isEmpty {
            parts.append(unit)
        }
        
        return parts.joined(separator: " ")
    }
}
