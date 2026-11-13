import from services.contacts { Contact, list_contacts, add_contact }

import ".styles.global.css";
import from .components.ContactBook { ContactBook }

def:pub app() -> JsxElement {
    return <ContactBook />;
}
