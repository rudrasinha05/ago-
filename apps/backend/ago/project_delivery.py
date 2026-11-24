"""PROJ-014 / PROJ-016: the prototype + integration service.

The AI project manager's stage progression calls this service at three
moments, and the Founder calls it once:

* opening implementation: a module plan must exist and be Founder-approved;
  the first unit (the working prototype) is started;
* testing a unit: its files are tested TOGETHER with everything integrated
  before it (complete regression), never alone;
* a unit passed tests and independent QA: it is integrated as a new source
  version and the next unit starts. Implementation passes only after the
  last module is integrated, so a prototype alone never completes a project;
* the Founder approves the module plan (POST .../modules/approve).

It never approves tasks, runs models, releases or spends.
"""
from __future__ import annotations

from uuid import UUID

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.project_module_store import ProjectModuleStore
from ago.project_modules import (
    api_summary, check_project_files, extract_modules, files_sha256, merge_unit,
    prototype_goal, test_names, unit_slug,
)


class ProjectDelivery:
    def __init__(self, connection: DatabaseConnection, *,
                 repositories: RepositoryScope | None = None):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def _store(self) -> ProjectModuleStore:
        return self.repositories.resolve(ProjectModuleStore)

    # -- Founder view and approval -------------------------------------------

    def view(self, *, tenant_id: str, founder_id: str, project_id: str) -> dict:
        for value in (tenant_id, founder_id, project_id):
            UUID(value)
        store = self._store()
        project = store.project(tenant_id, project_id)
        if project is None or str(project["founder_id"]) != founder_id:
            raise LookupError("Project not found")
        plan = store.plan(tenant_id, project_id)
        if plan is None:
            # Not proposed yet: show what AGO would plan from the brief.
            found = extract_modules(project["brief"])
            return {"kind": "ago_project_modules_v1", "status": "not_planned",
                    "preview": found["modules"], "deferred": found["deferred"], "units": [],
                    "integrated": 0, "total": 0, "latest_version": None}
        units = store.units(tenant_id, str(plan["id"]))
        latest = store.latest_version(tenant_id, project_id)
        return {
            "kind": "ago_project_modules_v1", "status": plan["status"], "source": plan["source"],
            "deferred": [c for c in plan["deferred"].split(",") if c],
            "decided_at": plan["decided_at"].isoformat() if plan["decided_at"] else None,
            "units": [{
                "id": str(u["id"]), "position": u["position"], "code": u["code"],
                "title": u["title"], "goal": u["goal"], "status": u["status"],
                "version": u["version"], "unittest_cases": u["unittest_cases"],
            } for u in units],
            "integrated": sum(1 for u in units if u["status"] == "integrated"),
            "total": len(units),
            "latest_version": ({"version": latest["version"], "files": len(latest["files"]),
                                "unittest_cases": latest["unittest_cases"],
                                "test_names": test_names(latest["files"])[:60]}
                               if latest else None),
        }

    def approve(self, *, tenant_id: str, founder_id: str, project_id: str) -> dict:
        """The Founder approves the proposed module plan (PROJ-016 step 3)."""
        for value in (tenant_id, founder_id, project_id):
            UUID(value)
        store = self._store()
        with self.connection.transaction():
            project = store.project(tenant_id, project_id)
            if project is None or str(project["founder_id"]) != founder_id:
                raise LookupError("Project not found")
            plan = store.plan(tenant_id, project_id, lock=True)
            if plan is None:
                raise ValueError("AGO has not proposed a module plan for this project yet")
            if plan["status"] == "proposed":
                store.approve_plan(tenant_id, str(plan["id"]), founder_id)
        return self.view(tenant_id=tenant_id, founder_id=founder_id, project_id=project_id)

    # -- stage progression hooks ---------------------------------------------

    def prepare_implementation(self, *, tenant_id: str, project_id: str,
                               architecture_text: str = "") -> dict:
        """Before implementation opens. Caller owns the transaction.

        Returns {"ready": True, "unit": {...}} once the plan is approved and the
        prototype unit is started, or {"ready": False, "state", "reason"}.
        """
        store = self._store()
        plan = store.plan(tenant_id, project_id, lock=True)
        if plan is None:
            project = store.project(tenant_id, project_id)
            source, found = "brief", extract_modules(project["brief"] if project else "")
            if not found["modules"]:
                source, found = "architecture", extract_modules(architecture_text)
            if not found["modules"]:
                return {"ready": False, "state": "module_plan_missing", "reason": (
                    "No module list was found in the brief or the approved architecture. "
                    "Add the modules to the brief as rows like 'M01<TAB>Name<TAB>What it does', "
                    "then advance again.")}
            units = [{"code": "PROTOTYPE", "title": "Working prototype",
                      "goal": prototype_goal(project["title"] if project else "the project")}]
            units += found["modules"]
            store.insert_plan(tenant_id, project_id, source=source,
                              deferred=",".join(found["deferred"]), units=units)
            return {"ready": False, "state": "module_plan_needs_approval", "reason": (
                "AGO proposed a module plan: a working prototype, then "
                + str(len(found["modules"])) + " modules ("
                + ", ".join(m["code"] for m in found["modules"])[:200] + ")"
                + (". Deferred for later: " + ", ".join(found["deferred"])[:200]
                   if found["deferred"] else "")
                + ". Review and approve it on the project page before implementation starts.")}
        if plan["status"] != "approved":
            return {"ready": False, "state": "module_plan_needs_approval", "reason": (
                "The module plan is waiting for the Founder's approval on the project page.")}
        unit = store.active_unit(tenant_id, project_id) or self._start_next(tenant_id, project_id, plan)
        if unit is None:
            return {"ready": False, "state": "all_units_integrated",
                    "reason": "Every unit of the module plan is already integrated."}
        return {"ready": True, "unit": unit}

    def _start_next(self, tenant_id: str, project_id: str, plan: dict) -> dict | None:
        store = self._store()
        nxt = next((u for u in store.units(tenant_id, str(plan["id"])) if u["status"] == "planned"), None)
        if nxt is None:
            return None
        latest = store.latest_version(tenant_id, project_id)
        store.start_unit(tenant_id, str(nxt["id"]), int(latest["version"]) if latest else 0)
        return store.active_unit(tenant_id, project_id)

    def is_modular(self, *, tenant_id: str, project_id: str) -> bool:
        plan = self._store().plan(tenant_id, project_id)
        return plan is not None and plan["status"] == "approved"

    def implementation_complete(self, *, tenant_id: str, project_id: str) -> bool:
        """True when there is no approved plan (legacy project) or every unit is integrated."""
        store = self._store()
        plan = store.plan(tenant_id, project_id)
        if plan is None or plan["status"] != "approved":
            return plan is None
        return all(u["status"] == "integrated" for u in store.units(tenant_id, str(plan["id"])))

    def unit_context(self, *, tenant_id: str, project_id: str) -> dict | None:
        """What the AI engineer is told about the unit in progress (prompt data)."""
        store = self._store()
        unit = store.active_unit(tenant_id, project_id)
        if unit is None:
            return None
        plan_units = store.units(tenant_id, str(unit["plan_id"]))
        latest = store.latest_version(tenant_id, project_id)
        existing = latest["files"] if latest else []
        return {
            "code": unit["code"], "title": unit["title"], "goal": unit["goal"],
            "slug": unit_slug(unit["code"], unit["title"]),
            "position": unit["position"], "total": len(plan_units),
            "existing_paths": sorted(f["path"] for f in existing)[:80],
            "api": api_summary(existing),
            "existing_tests": len(test_names(existing)),
        }

    def files_to_test(self, *, tenant_id: str, project_id: str, candidate: dict) -> dict | None:
        """For a unit in progress: the complete file set its tests must pass.

        None for a legacy (non-modular) project, whose candidate is tested alone.
        Raises ValueError when the unit tries to change an integrated file.
        """
        store = self._store()
        unit = store.active_unit(tenant_id, project_id)
        if unit is None:
            return None
        latest = store.latest_version(tenant_id, project_id)
        if (int(latest["version"]) if latest else 0) != int(unit["base_version"]):
            raise ValueError("The project source changed while this unit was in progress")
        files = merge_unit(latest["files"] if latest else [], candidate.get("files") or [])
        return {"unit": unit, "files": files, "base_version": int(unit["base_version"])}

    def integrate_passed_unit(self, *, tenant_id: str, project_id: str, task_id: str,
                              candidate: dict, cases: int) -> dict:
        """Integrate the unit whose task passed tests and QA; start the next one.

        Caller owns the transaction. The tests already ran on exactly this merged
        file set (same base version), so integration stores it unchanged.
        """
        store = self._store()
        unit = store.active_unit(tenant_id, project_id)
        if unit is None:
            raise ValueError("No unit is in progress for this project")
        merged = self.files_to_test(tenant_id=tenant_id, project_id=project_id, candidate=candidate)
        files = merged["files"]
        check_project_files(files)
        store.integrate(tenant_id, project_id, unit_id=str(unit["id"]), task_id=task_id,
                        version=merged["base_version"] + 1, files=files,
                        files_sha256=files_sha256(files), cases=max(1, int(cases)))
        plan = store.plan(tenant_id, project_id)
        nxt = self._start_next(tenant_id, project_id, plan)
        return {"integrated": {"code": unit["code"], "title": unit["title"],
                               "version": merged["base_version"] + 1, "files": len(files),
                               "unittest_cases": int(cases)},
                "next": nxt}

    def regression_evidence(self, *, tenant_id: str, project_id: str) -> str:
        """AGO's record of the complete integrated product's tests ('' if none)."""
        store = self._store()
        latest = store.latest_version(tenant_id, project_id)
        plan = store.plan(tenant_id, project_id)
        if latest is None or plan is None:
            return ""
        units = store.units(tenant_id, str(plan["id"]))
        done = [u["code"] for u in units if u["status"] == "integrated"]
        names = test_names(latest["files"])
        return ("AGO REGRESSION EVIDENCE: the integrated product (version "
                + str(latest["version"]) + ", " + str(len(latest["files"])) + " files: "
                + ", ".join(done)[:240] + ") passed ALL " + str(latest["unittest_cases"])
                + " unittest case(s) together in offline Docker, run by AGO: "
                + ", ".join(names)[:420] + ". (Recorded by AGO, not written by a model.)")[:1100]

    def task_test(self, *, tenant_id: str, task_id: str) -> dict | None:
        return self._store().task_test(tenant_id, task_id)

    def link_next_unit_task(self, *, tenant_id: str, unit_id: str, plan_step_id: str,
                            previous_task_id: str, task_id: str) -> None:
        """Caller owns the transaction."""
        self._store().link_unit_task(tenant_id, unit_id=unit_id, plan_step_id=plan_step_id,
                                     previous_task_id=previous_task_id, task_id=task_id)
