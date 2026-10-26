# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "function",
  "task_type": "farm",
  "fp": "angermaster11_webx__backend_app_models_menu_py::MenuCategoryUpdate",
  "origin_file": "farm_dataset.jsonl",
  "origin_id": "angermaster11_webx__backend_app_models_menu_py::MenuCategoryUpdate",
  "verification": "check+behavioral",
  "n_tokens": 1859,
  "n_answer_tokens": 269
}
```

## SYSTEM

```
You are a helpful assistant.
```

## USER

Given the following Jac graph schema, write CRUD walkers (create, list, delete, and update where applicable) for the 'MenuCategoryUpdate' node. Respond with only the code.

```jac
node Addon {
    has name: str;
    has price: float;
    has is_available: bool = True;
}

node Variant {
    has name: str;
    has price: float;
    has is_available: bool = True;
}

node NutritionInfo {
    has calories: int | None = None;
    has protein: float | None = None;
    has carbs: float | None = None;
    has fat: float | None = None;
}

node MenuCategory {
    has restaurant_id: str;
    has name: str;
    has available_days: list[str];
    has created_at: str;
    has updated_at: str;
    has branch_id: str | None = None;
    has description: str | None = None;
    has image_url: str | None = None;
    has display_order: int = 0;
    has is_active: bool = True;
    has available_from: str | None = None;
    has available_until: str | None = None;
}

node MenuItem {
    has restaurant_id: str;
    has category_id: str;
    has name: str;
    has description: str;
    has base_price: float;
    has food_type: str;
    has created_at: str;
    has updated_at: str;
    has branch_id: str | None = None;
    has image_url: str | None = None;
    has discount_percentage: float = 0.0;
    has final_price: float = 0.0;
    has spice_level: str | None = None;
    has variants: list[str] = [];
    has addons: list[str] = [];
    has customization_options: list[str] = [];
    has is_available: bool = True;
    has is_bestseller: bool = False;
    has is_new: bool = False;
    has is_recommended: bool = False;
    has is_daily_special: bool = False;
    has preparation_time_minutes: int = 15;
    has nutrition_info: str | None = None;
    has allergens: list[str] = [];
    has tags: list[str] = [];
    has order_count: int = 0;
    has avg_rating: float = 0.0;
    has display_order: int = 0;
}

node MenuCategoryCreate {
    has name: str;
    has available_days: list[str];
    has description: str | None = None;
    has image_url: str | None = None;
    has display_order: int = 0;
    has branch_id: str | None = None;
    has available_from: str | None = None;
    has available_until: str | None = None;
}

node MenuCategoryUpdate {
    has name: str | None = None;
    has description: str | None = None;
    has image_url: str | None = None;
    has display_order: int | None = None;
    has is_active: bool | None = None;
    has available_from: str | None = None;
    has available_until: str | None = None;
    has available_days: list[str] | None = None;
}

node MenuItemCreate {
    has category_id: str;
    has name: str;
    has description: str;
    has base_price: float;
    has food_type: str;
    has image_url: str | None = None;
    has discount_percentage: float = 0.0;
    has spice_level: str | None = None;
    has variants: list[str] = [];
    has addons: list[str] = [];
    has customization_options: list[str] = [];
    has preparation_time_minutes: int = 15;
    has nutrition_info: str | None = None;
    has allergens: list[str] = [];
    has tags: list[str] = [];
    has branch_id: str | None = None;
    has display_order: int = 0;
}

node MenuItemUpdate {
    has category_id: str | None = None;
    has name: str | None = None;
    has description: str | None = None;
    has image_url: str | None = None;
    has base_price: float | None = None;
    has discount_percentage: float | None = None;
    has food_type: str | None = None;
    has spice_level: str | None = None;
    has variants: list[str] | None = None;
    has addons: list[str] | None = None;
    has customization_options: list[str] | None = None;
    has is_available: bool | None = None;
    has is_bestseller: bool | None = None;
    has is_new: bool | None = None;
    has is_recommended: bool | None = None;
    has is_daily_special: bool | None = None;
    has preparation_time_minutes: int | None = None;
    has nutrition_info: str | None = None;
    has allergens: list[str] | None = None;
    has tags: list[str] | None = None;
    has display_order: int | None = None;
}

node MenuCategoryResponse {
    has restaurant_id: str;
    has name: str;
    has display_order: int;
    has is_active: bool;
    has available_days: list[str];
    has branch_id: str | None = None;
    has description: str | None = None;
    has image_url: str | None = None;
    has available_from: str | None = None;
    has available_until: str | None = None;
}

node MenuItemResponse {
    has restaurant_id: str;
    has category_id: str;
    has name: str;
    has description: str;
    has base_price: float;
    has discount_percentage: float;
    has final_price: float;
    has food_type: str;
    has variants: list[str];
    has addons: list[str];
    has customization_options: list[str];
    has is_available: bool;
    has is_bestseller: bool;
    has is_new: bool;
    has is_recommended: bool;
    has is_daily_special: bool;
    has preparation_time_minutes: int;
    has allergens: list[str];
    has tags: list[str];
    has avg_rating: float;
    has display_order: int;
    has branch_id: str | None = None;
    has image_url: str | None = None;
    has spice_level: str | None = None;
    has nutrition_info: str | None = None;
}
```

## ASSISTANT

walker:pub create_MenuCategoryUpdate {
    has name: str | None = None; has description: str | None = None; has image_url: str | None = None;
    has display_order: int | None = None; has is_active: bool | None = None;
    has available_from: str | None = None; has available_until: str | None = None;
    has available_days: list[str] | None = None;
    can go with Root entry {
        new = here ++> MenuCategoryUpdate(
            name=self.name, description=self.description, image_url=self.image_url,
            display_order=self.display_order, is_active=self.is_active, available_from=self.available_from,
            available_until=self.available_until, available_days=self.available_days
        );
        report new;
    }
}
walker:pub list_MenuCategoryUpdate { can go with Root entry { report [-->[?:MenuCategoryUpdate]]; } }
walker:pub update_MenuCategoryUpdate { has val: str | None; can go with MenuCategoryUpdate entry { here.description = self.val; report here; } }
walker:pub delete_MenuCategoryUpdate { can go with MenuCategoryUpdate entry { del here; report "deleted"; } }
