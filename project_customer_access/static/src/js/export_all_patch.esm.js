import {registry} from "@web/core/registry";
import {user} from "@web/core/user";

const cogMenuRegistry = registry.category("cogMenu");

const exportAllItem = cogMenuRegistry.get("export-all-menu");

const originalIsDisplayed = exportAllItem.isDisplayed;

exportAllItem.isDisplayed = async (env) => {
    const baseCondition = await originalIsDisplayed(env);
    const hasMyCustomGroup = await user.hasGroup(
        "project_customer_access.group_manager"
    );
    return baseCondition || hasMyCustomGroup;
};
