"""Independent behavior checks for Rui/pm project hierarchy slice."""

import from models.Project { create_root_project, create_sub_project, get_project, get_sub_projects, get_tasks, create_task }
import from walkers { approve_project, approve_task, delete_project, delete_task }

test "nested project and task relationships" {
    parent = create_root_project("Release", "Ship a release");
    child = create_sub_project(jid(parent), "Docs", "Write docs");
    assert child is not None;
    assert get_project(jid(child)) is not None;
    assert len(get_sub_projects(jid(parent))) == 1;
    task = create_task(jid(child), "Draft the release notes");
    assert task is not None;
    assert len(get_tasks(jid(child))) == 1;
    assert delete_task(jid(child), jid(task));
    assert len(get_tasks(jid(child))) == 0;
    assert delete_project(jid(parent));
    assert get_project(jid(parent)) is None;
}

test "approval traverses draft children" {
    parent = create_root_project("Launch", "Prepare launch");
    child = parent.draft_sub_project("Website", "Publish website");
    task = child.draft_task("Prepare landing page");
    assert child.is_draft;
    assert task.is_draft;
    assert approve_task(jid(child), jid(task));
    assert not task.is_draft;
    assert approve_project(jid(parent));
    assert not child.is_draft;
    assert delete_project(jid(parent));
}
