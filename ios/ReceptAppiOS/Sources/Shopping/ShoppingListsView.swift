import SwiftUI

struct ShoppingListsView: View {
    @EnvironmentObject private var session: SessionController

    @State private var lists: [ShoppingListDTO] = []
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil
    @State private var showCreateAlert: Bool = false
    @State private var newListName: String = ""

    var body: some View {
        NavigationStack {
            Group {
                if lists.isEmpty && !isLoading {
                    EmptyStateView(
                        iconName: "cart",
                        title: "Inga inköpslistor",
                        message: "Skapa en ny lista för att komma igång.",
                        actionTitle: "Skapa lista",
                        action: {
                            newListName = ""
                            showCreateAlert = true
                        }
                    )
                } else {
                    List {
                        ForEach(lists) { list in
                            NavigationLink(value: list) {
                                ShoppingListRow(list: list)
                            }
                        }
                        .onDelete(perform: deleteList)
                    }
                }
            }
            .overlay {
                if isLoading && lists.isEmpty {
                    ProgressView("Laddar listor...")
                }
            }
            .navigationTitle("Inköpslistor")
            .listStyle(.insetGrouped)
            .navigationDestination(for: ShoppingListDTO.self) { list in
                ShoppingListDetailView(list: list)
            }
            .alert("Ny stående lista", isPresented: $showCreateAlert) {
                TextField("Namn", text: $newListName)
                Button("Avbryt", role: .cancel) { }
                Button("Skapa") {
                    createList()
                }
            } message: {
                Text("Ange namn för den nya stående inköpslistan.")
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button {
                            newListName = ""
                            showCreateAlert = true
                        } label: {
                            Label("Ny lista", systemImage: "plus")
                        }

                        Button("Logga ut", role: .destructive) { session.logout() }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }

                if isLoading {
                    ToolbarItem(placement: .topBarLeading) {
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
                await load()
            }
            .refreshable {
                await load()
            }
        }
    }

    private func createList() {
        guard let token = session.token, !newListName.isEmpty else { return }
        
        Task {
            do {
                _ = try await APIClient.shared.createShoppingList(name: newListName, isRecurring: true, token: token)
                await load()
            } catch {
                errorMessage = APIError.userFacingMessage(for: error)
            }
        }
    }

    private func load() async {
        guard let token = session.token else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            lists = try await APIClient.shared.fetchShoppingLists(token: token)
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }

    private func deleteList(at offsets: IndexSet) {
        guard let token = session.token else { return }
        
        for index in offsets {
            let list = lists[index]
            Task {
                do {
                    try await APIClient.shared.deleteShoppingList(id: list.id, token: token)
                    await load()
                } catch {
                    errorMessage = APIError.userFacingMessage(for: error)
                }
            }
        }
    }
}

private struct ShoppingListRow: View {
    let list: ShoppingListDTO

    private var iconName: String {
        list.isRecurring ? "arrow.triangle.2.circlepath" : "cart"
    }

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.secondary.opacity(0.10))
                .frame(width: 44, height: 44)
                .overlay {
                    Image(systemName: iconName)
                        .foregroundStyle(.secondary)
                }

            VStack(alignment: .leading, spacing: 4) {
                Text(list.name)
                    .font(.headline)

                HStack(spacing: 8) {
                    if let count = list.itemCount {
                        Label("\(count)", systemImage: "checklist")
                            .labelStyle(.titleAndIcon)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    if let date = list.updatedAt {
                        Label(date.formatted(date: .abbreviated, time: .shortened), systemImage: "clock")
                            .labelStyle(.titleAndIcon)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                if list.isRecurring {
                    Text("Stående")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer(minLength: 0)
        }
        .padding(.vertical, 2)
        .accessibilityElement(children: .combine)
    }
}
