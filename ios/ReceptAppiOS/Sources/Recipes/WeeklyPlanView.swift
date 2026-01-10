import SwiftUI

struct DaySelection: Identifiable {
    let id: String
}

struct WeeklyPlanView: View {
    @EnvironmentObject private var session: SessionController
    @State private var plan: [WeeklyPlanDTO] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    
    @State private var showPickerForDay: DaySelection?
    @State private var showSaveAlert = false
    @State private var saveMenuName = ""
    @State private var saveMenuServings = "4"

    private let daysOrder = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    private let dayNames: [String: String] = [
        "mon": "Måndag", "tue": "Tisdag", "wed": "Onsdag",
        "thu": "Torsdag", "fri": "Fredag", "sat": "Lördag", "sun": "Söndag"
    ]

    var body: some View {
        NavigationStack {
            List {
                if plan.isEmpty && !isLoading {
                    Text("Ingen veckoplanering hittades.")
                        .foregroundStyle(.secondary)
                }

                ForEach(daysOrder, id: \.self) { dayCode in
                    Section {
                        let dayItems = plan.filter { $0.day == dayCode }
                        ForEach(dayItems) { item in
                            NavigationLink(destination: RecipeDetailLoader(recipeId: item.recipe)) {
                                Text(item.recipeTitle)
                                    .font(.body)
                            }
                        }
                        .onDelete { indexSet in
                            deleteItems(at: indexSet, day: dayCode)
                        }
                        
                        Button {
                            showPickerForDay = DaySelection(id: dayCode)
                        } label: {
                            Label("Lägg till recept", systemImage: "plus")
                        }
                    } header: {
                        Text(dayNames[dayCode] ?? dayCode)
                    }
                }
            }
            .navigationTitle("Veckoplan")
            .listStyle(.insetGrouped)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button("Slumpa vecka", systemImage: "dice") {
                            Task { await randomize() }
                        }
                        Button("Spara som meny", systemImage: "square.and.arrow.down") {
                            saveMenuName = ""
                            saveMenuServings = "4"
                            showSaveAlert = true
                        }
                        NavigationLink {
                            WeeklyMenuListView()
                        } label: {
                            Label("Mina menyer", systemImage: "list.bullet")
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
            .task {
                await load()
            }
            .refreshable {
                await load()
            }
            .overlay {
                if isLoading && plan.isEmpty {
                    ProgressView()
                }
            }
            .sheet(item: $showPickerForDay) { selection in
                RecipePickerView { recipe in
                    Task { await addRecipe(day: selection.id, recipe: recipe) }
                }
            }
            .alert("Spara veckomeny", isPresented: $showSaveAlert) {
                TextField("Namn (valfritt)", text: $saveMenuName)
                TextField("Antal portioner", text: $saveMenuServings)
                    .keyboardType(.numberPad)
                Button("Avbryt", role: .cancel) { }
                Button("Spara") {
                    Task { await saveAsMenu() }
                }
            } message: {
                Text("Ange namn och antal portioner för menyn.")
            }
            .safeAreaInset(edge: .bottom) {
                if let errorMessage {
                    Text(errorMessage)
                        .frame(maxWidth: .infinity)
                        .padding(12)
                        .background(.thinMaterial)
                        .foregroundStyle(.red)
                }
            }
        }
    }

    private func load() async {
        guard let token = session.token else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            plan = try await APIClient.shared.fetchWeeklyPlan(token: token)
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }
    
    private func randomize() async {
        guard let token = session.token else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            plan = try await APIClient.shared.randomizeWeeklyPlan(token: token)
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }

    private func saveAsMenu() async {
        guard let token = session.token else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        
        let servings = Int(saveMenuServings)
        
        do {
            try await APIClient.shared.saveWeeklyPlanAsMenu(name: saveMenuName, servings: servings, token: token)
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }
    
    private func addRecipe(day: String, recipe: RecipeDTO) async {
        guard let token = session.token else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            let newItem = try await APIClient.shared.addToWeeklyPlan(day: day, recipeId: recipe.id, token: token)
            plan.append(newItem)
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }
    
    private func deleteItems(at offsets: IndexSet, day: String) {
        guard let token = session.token else { return }
        let dayItems = plan.filter { $0.day == day }
        
        for index in offsets {
            let item = dayItems[index]
            // Remove from local state immediately
            if let planIndex = plan.firstIndex(where: { $0.id == item.id }) {
                plan.remove(at: planIndex)
            }
            
            Task {
                do {
                    try await APIClient.shared.deleteFromWeeklyPlan(id: item.id, token: token)
                } catch {
                    errorMessage = APIError.userFacingMessage(for: error)
                }
            }
        }
    }
}

struct RecipeDetailLoader: View {
    let recipeId: Int
    @EnvironmentObject private var session: SessionController
    @State private var recipe: RecipeDTO?
    @State private var error: Error?
    
    var body: some View {
        Group {
            if let recipe {
                RecipeDetailView(recipe: recipe)
            } else if let error {
                Text("Kunde inte ladda recept: \(error.localizedDescription)")
            } else {
                ProgressView()
                    .task {
                        guard let token = session.token else { return }
                        do {
                            recipe = try await APIClient.shared.fetchRecipe(id: recipeId, token: token)
                        } catch {
                            self.error = error
                        }
                    }
            }
        }
    }
}

struct WeeklyMenuListView: View {
    @EnvironmentObject private var session: SessionController
    @State private var menus: [WeeklyMenuDTO] = []
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        List {
            if menus.isEmpty && !isLoading {
                Text("Inga sparade menyer hittades.")
                    .foregroundStyle(.secondary)
            }

            ForEach(menus) { menu in
                NavigationLink(destination: WeeklyMenuDetailView(menu: menu)) {
                    VStack(alignment: .leading) {
                        Text(menu.name)
                            .font(.headline)
                        Text("Skapad: \(menu.createdAt.formatted(date: .numeric, time: .omitted))")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .onDelete(perform: deleteMenu)
        }
        .navigationTitle("Sparade menyer")
        .task {
            await loadMenus()
        }
        .refreshable {
            await loadMenus()
        }
        .overlay {
            if isLoading && menus.isEmpty {
                ProgressView()
            }
        }
        .alert("Fel", isPresented: Binding<Bool>(
            get: { errorMessage != nil },
            set: { _ in errorMessage = nil }
        )) {
            Button("OK") { errorMessage = nil }
        } message: {
            Text(errorMessage ?? "")
        }
    }

    private func loadMenus() async {
        guard let token = session.token else { return }
        isLoading = true
        defer { isLoading = false }
        
        do {
            menus = try await APIClient.shared.fetchWeeklyMenus(token: token)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func deleteMenu(at offsets: IndexSet) {
        guard let token = session.token else { return }
        
        for index in offsets {
            let menu = menus[index]
            Task {
                do {
                    try await APIClient.shared.deleteWeeklyMenu(id: menu.id, token: token)
                    await loadMenus()
                } catch {
                    errorMessage = "Kunde inte ta bort meny: \(error.localizedDescription)"
                }
            }
        }
    }
}

struct WeeklyMenuDetailView: View {
    let menu: WeeklyMenuDTO
    private let dayNames: [String: String] = [
        "mon": "Måndag", "tue": "Tisdag", "wed": "Onsdag",
        "thu": "Torsdag", "fri": "Fredag", "sat": "Lördag", "sun": "Söndag"
    ]
    private let daysOrder = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    var body: some View {
        List {
            ForEach(daysOrder, id: \.self) { dayCode in
                let dayItems = menu.items.filter { $0.day == dayCode }
                if !dayItems.isEmpty {
                    Section(header: Text(dayNames[dayCode] ?? dayCode)) {
                        ForEach(dayItems) { item in
                            NavigationLink(destination: RecipeDetailLoader(recipeId: item.recipe)) {
                                Text(item.recipeTitle)
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle(menu.name)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                NavigationLink(destination: WeeklyMenuShoppingListView(menuId: menu.id, menuName: menu.name)) {
                    Label("Inköpslista", systemImage: "cart")
                }
            }
        }
    }
}

struct WeeklyMenuShoppingListView: View {
    let menuId: Int
    let menuName: String
    @EnvironmentObject private var session: SessionController
    @State private var categories: [WeeklyMenuShoppingListCategoryDTO] = []
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        List {
            if categories.isEmpty && !isLoading {
                Text("Inga ingredienser hittades.")
                    .foregroundStyle(.secondary)
            }
            
            ForEach(categories) { category in
                Section(header: Text(category.category)) {
                    ForEach(category.items) { item in
                        HStack {
                            Text(item.name)
                            Spacer()
                            if !item.amount.isEmpty {
                                Text("\(item.amount) \(item.unit)")
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle("Inköpslista")
        .task {
            await load()
        }
        .overlay {
            if isLoading {
                ProgressView()
            }
        }
        .alert("Fel", isPresented: Binding<Bool>(
            get: { errorMessage != nil },
            set: { _ in errorMessage = nil }
        )) {
            Button("OK") { errorMessage = nil }
        } message: {
            Text(errorMessage ?? "")
        }
    }
    
    private func load() async {
        guard let token = session.token else { return }
        isLoading = true
        defer { isLoading = false }
        
        do {
            categories = try await APIClient.shared.fetchWeeklyMenuShoppingList(menuId: menuId, token: token)
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
