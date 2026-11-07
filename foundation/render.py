#!/usr/bin/env python3
"""Render a pinned, offline native plugin from a strict declarative profile.

The source commit identifies the foundation checkout, not the generated candidate's
later Git commit. Candidate/install identity must be checked separately.
"""
import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

FOUNDATION = Path(__file__).resolve().parent
FOUNDATION_REPOSITORY = "https://github.com/Gabedave/fintech-agent-toolkit"
PROFILE_KEYS = {
    "schema_version", "plugin_name", "plugin_version", "marketplace", "company",
    "router", "router_title", "audience", "repository_url", "adapter_revision",
    "discovery", "delivery_default",
}
SLUG = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
SEMVER = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?\Z")
TEXT = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .,&'()/+\-]*\Z")
TOKEN = re.compile(r"\{\{([A-Z_]+)\}\}")
LOCK = "foundation-lock.json"


class Invalid(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def file_mode(path):
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode not in (0o644, 0o755):
        raise Invalid(f"unsupported file mode {mode:04o}: {path}; expected 0644 or 0755")
    return f"{mode:04o}"


def file_record(content, mode):
    return {"sha256": digest(content), "mode": mode}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Invalid(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    no_symlinks(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise Invalid(f"cannot read JSON {path}: {error}") from error


def exact_keys(value, keys, label):
    if not isinstance(value, dict) or set(value) != keys:
        raise Invalid(f"{label} keys must be exactly: {', '.join(sorted(keys))}")


def no_symlinks(path):
    """Reject traversal before lexical containment checks; never resolve symlinks away."""
    if ".." in path.parts:
        raise Invalid(f"parent traversal is not allowed: {path}; use a canonical path")
    for item in (path, *path.parents):
        if item.is_symlink():
            raise Invalid(f"symlink is not allowed: {item}; use a canonical path")


def validate_profile(path):
    no_symlinks(path)
    profile = read_json(path)
    exact_keys(profile, PROFILE_KEYS, "profile")
    if type(profile["schema_version"]) is not int or profile["schema_version"] != 1:
        raise Invalid("unsupported profile schema_version")
    for key in ("plugin_name", "marketplace", "router"):
        value = profile[key]
        if not isinstance(value, str) or len(value) > 64 or not SLUG.fullmatch(value):
            raise Invalid(f"unsafe profile {key}")
    for key in ("company", "router_title", "audience"):
        value = profile[key]
        if not isinstance(value, str) or len(value) > 120 or not TEXT.fullmatch(value) or value != value.strip():
            raise Invalid(f"{key} must be short single-line plain text")
    version = profile["plugin_version"]
    if not isinstance(version, str) or len(version) > 64 or not SEMVER.fullmatch(version):
        raise Invalid("plugin_version must be an explicit semantic version")
    revision = profile["adapter_revision"]
    if not isinstance(revision, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", revision):
        raise Invalid("adapter_revision must be an explicit safe identifier")
    url = profile["repository_url"]
    if not isinstance(url, str) or not re.fullmatch(r"https://[A-Za-z0-9.-]+(?::[0-9]+)?(?:/[A-Za-z0-9._~/-]*)?", url):
        raise Invalid("repository_url must be an HTTPS repository URL")
    parsed = urlsplit(url)
    if not parsed.hostname or parsed.username or parsed.password:
        raise Invalid("repository_url must identify a repository without credentials")
    if profile["delivery_default"] not in ("pull-request", "local-only"):
        raise Invalid("delivery_default must be pull-request or local-only")
    discovery = profile["discovery"]
    if not isinstance(discovery, dict) or not discovery or len(discovery) > 20:
        raise Invalid("discovery must map repository roles to relative hints")
    for role, hints in discovery.items():
        if not isinstance(role, str) or len(role) > 64 or not SLUG.fullmatch(role):
            raise Invalid("unsafe discovery role")
        if not isinstance(hints, list) or not hints or len(hints) > 30:
            raise Invalid("discovery hints must be non-empty lists")
        for hint in hints:
            if (not isinstance(hint, str) or len(hint) > 180
                    or not re.fullmatch(r"[A-Za-z0-9_.*?/-]+", hint)
                    or hint.startswith("/") or any(part in ("", ".", "..") for part in hint.split("/"))):
                raise Invalid("discovery hints must be safe relative paths or globs")
    return profile


def substitutions(profile):
    discovery = "\n".join(
        f"- {role}: " + ", ".join(f"`{hint}`" for hint in hints)
        for role, hints in sorted(profile["discovery"].items())
    )
    discovery += "\n\nThese are unverified discovery hints. Confirm repository ownership and local instructions before acting."
    delivery = "Default delivery: " + profile["delivery_default"] + ". "
    if profile["delivery_default"] == "local-only":
        delivery += "Only local editing is included by default; additional stages require explicit user authorization. Keep work local; do not push, create or update remote pull requests, publish, merge, or deploy without explicit user authorization."
    else:
        delivery += "For non-trivial implementation in repositories adopting this default, requested delivery includes edit, commit, push, update an existing or open a new pull request, and CI follow-through unless the user or repository narrows those stages. Respect local-only, no-commit, no-push, no-PR, no-CI, read-only, and requested-draft restrictions. Make ready work reviewable."
    delivery += " Merge, deployment, ticket updates, and team messages require separate explicit authorization. Personal or user-wide active plugin/skill installation changes are a separate authority boundary; classify those actions when relevant and perform them only within applicable explicit task/session authorization. Honor authorization already granted within its scope, without asking again or extending it. Authorized product-repository work and owned disposable fixture setup retain their existing task scope. Readiness and green CI never grant merge or deployment authority."
    return {
        "PLUGIN_NAME": profile["plugin_name"], "PLUGIN_VERSION": profile["plugin_version"],
        "MARKETPLACE": profile["marketplace"], "COMPANY": profile["company"],
        "ROUTER": profile["router"], "ROUTER_TITLE": profile["router_title"],
        "AUDIENCE": profile["audience"], "REPOSITORY_URL": profile["repository_url"],
        "DISCOVERY": discovery, "DELIVERY_POLICY": delivery,
    }


def substitute(text, tokens):
    def replacement(match):
        if match[1] not in tokens:
            raise Invalid(f"unknown foundation token: {match[0]}")
        return tokens[match[1]]
    result = TOKEN.sub(replacement, text)
    if re.search(r"\{\{[A-Z_]", result):
        raise Invalid("unresolved or malformed foundation token")
    return result


def substitute_json(value, tokens):
    if isinstance(value, str):
        return substitute(value, tokens)
    if isinstance(value, list):
        return [substitute_json(item, tokens) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            rendered_key = substitute(key, tokens)
            if rendered_key in result:
                raise Invalid("JSON keys collide after substitution")
            result[rendered_key] = substitute_json(item, tokens)
        return result
    return value


def generate(profile, commit):
    no_symlinks(FOUNDATION)
    version = read_json(FOUNDATION / "version.json")
    exact_keys(version, {"schema_version", "version"}, "foundation version")
    if type(version["schema_version"]) is not int or version["schema_version"] != 1:
        raise Invalid("unsupported foundation schema_version")
    if not isinstance(version["version"], str) or not SEMVER.fullmatch(version["version"]):
        raise Invalid("foundation version must be semantic versioning")
    bundle = FOUNDATION / "plugin"
    if not bundle.is_dir():
        raise Invalid("foundation/plugin bundle is missing")
    no_symlinks(bundle)
    source_files = []
    bundle_files = []
    for path in sorted(FOUNDATION.rglob("*")):
        if "__pycache__" in path.relative_to(FOUNDATION).parts:
            continue
        no_symlinks(path)
        if not path.is_dir() and not path.is_file():
            raise Invalid(f"unsupported foundation entry: {path}")
        if path.is_file():
            source_files.append(path)
            if bundle in path.parents:
                bundle_files.append(path)
    source_hashes = {path.relative_to(FOUNDATION).as_posix(): file_record(path.read_bytes(), file_mode(path))
                     for path in source_files}
    tokens = substitutions(profile)
    files = {}
    modes = {}
    for path in bundle_files:
        relative = substitute(path.relative_to(bundle).as_posix(), tokens)
        if any(part in ("", ".", "..") for part in relative.split("/")) or relative.startswith("/"):
            raise Invalid("unsafe generated path")
        destination = f"plugins/{profile['plugin_name']}/{relative}"
        if destination in files:
            raise Invalid("generated file paths collide")
        modes[destination] = source_hashes[path.relative_to(FOUNDATION).as_posix()]["mode"]
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeError as error:
            raise Invalid(f"foundation source must be UTF-8 text: {path}") from error
        if path.suffix == ".json":
            value = substitute_json(read_json(path), tokens)
            if relative == f"skills/{profile['router']}/references/routing-contract.json":
                authorization = value.get("authorization") if isinstance(value, dict) else None
                original_actions = ["edit", "commit", "push", "open-pull-request"]
                if not isinstance(authorization, dict) or authorization.get("implementation_delivery_actions") != original_actions:
                    raise Invalid("unsupported foundation routing delivery contract")
                authorization["implementation_delivery_actions"] = (
                    original_actions if profile["delivery_default"] == "pull-request" else ["edit"]
                )
            files[destination] = json_bytes(value)
        else:
            files[destination] = substitute(content, tokens).encode("utf-8")
    manifest_path = f"plugins/{profile['plugin_name']}/.codex-plugin/plugin.json"
    if manifest_path not in files:
        raise Invalid("foundation must contain a native .codex-plugin/plugin.json")
    manifest = json.loads(files[manifest_path])
    if manifest.get("name") != profile["plugin_name"] or manifest.get("version") != profile["plugin_version"]:
        raise Invalid("native manifest does not match profile identity")
    router = f"plugins/{profile['plugin_name']}/skills/{profile['router']}/SKILL.md"
    if router not in files:
        raise Invalid("foundation is missing the profile router entrypoint")
    files[".agents/plugins/marketplace.json"] = json_bytes({
        "name": profile["marketplace"], "interface": {"displayName": profile["company"]},
        "plugins": [{"name": profile["plugin_name"],
                     "source": {"source": "local", "path": f"./plugins/{profile['plugin_name']}"},
                     "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                     "category": "Productivity"}],
    })
    modes[".agents/plugins/marketplace.json"] = "0644"
    foundation = {"repository": FOUNDATION_REPOSITORY, "version": version["version"],
                  "commit": commit, "digest": digest(canonical(source_hashes))}
    identity = {
        "schema_version": 2, "canonical_repository": profile["repository_url"],
        "source_commit": commit, "plugin_name": profile["plugin_name"],
        "plugin_version": profile["plugin_version"], "foundation": foundation,
        "adapter_revision": profile["adapter_revision"], "profile_digest": digest(canonical(profile)),
    }
    prefix = f"plugins/{profile['plugin_name']}/"
    content_files = {name[len(prefix):]: file_record(content, modes[name]) for name, content in sorted(files.items())
                     if name.startswith(prefix)}
    provenance_path = prefix + ".codex-plugin/foundation-provenance.json"
    if provenance_path in files:
        raise Invalid("foundation source must not supply generated provenance")
    files[provenance_path] = json_bytes(dict(identity, content_files=content_files,
                                            content_digest=digest(canonical(content_files))))
    modes[provenance_path] = "0644"
    hashes = {name: file_record(content, modes[name]) for name, content in sorted(files.items())}
    lock = dict(identity, generated_tree_digest=digest(canonical(hashes)), files=hashes)
    files[LOCK] = json_bytes(lock)
    modes[LOCK] = "0644"
    return files, modes


def validate_destination(output, profile, files):
    no_symlinks(output)
    if output == FOUNDATION or FOUNDATION in output.parents:
        raise Invalid("output cannot be inside the foundation source")
    for relative in files:
        target = output / relative
        no_symlinks(target)
        if target.exists() and not target.is_file():
            raise Invalid(f"generated file destination is not a file: {target}")
    marketplace_name = ".agents/plugins/marketplace.json"
    marketplace = output / marketplace_name
    if marketplace.exists() and read_json(marketplace) != json.loads(files[marketplace_name]):
        raise Invalid("existing marketplace has another identity, plugin, or custom metadata; reconcile explicitly or use clean output")
    lock_path = output / LOCK
    if not lock_path.exists():
        occupied = [name for name in files if (output / name).exists()]
        if occupied:
            raise Invalid("initial managed destination must be clean; existing files require explicit reconciliation: "
                          + ", ".join(sorted(occupied)))
    else:
        if file_mode(lock_path) != "0644":
            raise Invalid("existing root lock mode differs from its required 0644; preserve and reconcile explicitly")
        existing = read_json(lock_path)
        expected = json.loads(files[LOCK])
        exact_keys(existing, set(expected), "existing foundation lock")
        if (type(existing["schema_version"]) is not int or existing["schema_version"] != 2
                or existing["plugin_name"] != profile["plugin_name"]
                or existing["canonical_repository"] != profile["repository_url"]):
            raise Invalid("existing foundation lock belongs to another profile or unsupported schema; use reconciled clean output")
        previous_files = existing["files"]
        if not isinstance(previous_files, dict) or not previous_files:
            raise Invalid("existing ownership lock has no complete managed file map")
        for name, record in previous_files.items():
            if name not in files or name == LOCK:
                raise Invalid("existing lock names unsupported managed paths; reconcile explicitly")
            exact_keys(record, {"sha256", "mode"}, "existing file record")
            if (not isinstance(record["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])
                    or record["mode"] not in ("0644", "0755")):
                raise Invalid("existing ownership lock has an unsupported file record")
            target = output / name
            if not target.is_file():
                raise Invalid(f"existing managed file is missing: {name}; preserve and reconcile explicitly")
            actual_record = file_record(target.read_bytes(), file_mode(target))
            # A structurally identical owned marketplace may differ in whitespace;
            # the complete metadata comparison above establishes safe ownership.
            if actual_record["mode"] != record["mode"] or (actual_record["sha256"] != record["sha256"] and name != marketplace_name):
                raise Invalid(f"existing managed content or mode differs from ownership lock: {name}; preserve and reconcile explicitly")
        if existing["generated_tree_digest"] != digest(canonical(previous_files)):
            raise Invalid("existing ownership lock has an inconsistent tree digest")
        unowned = [name for name in files if name != LOCK and (output / name).exists() and name not in previous_files]
        if unowned:
            raise Invalid("existing planned files lack positive ownership: " + ", ".join(sorted(unowned)))
    plugin = output / "plugins" / profile["plugin_name"]
    actual = set()
    if plugin.exists():
        if not plugin.is_dir():
            raise Invalid("generated plugin destination is not a directory")
        for path in plugin.rglob("*"):
            no_symlinks(path)
            if not path.is_dir() and not path.is_file():
                raise Invalid(f"unsupported generated entry: {path}")
            if path.is_file():
                actual.add(path.relative_to(output).as_posix())
    extras = actual - set(files)
    if extras:
        raise Invalid("unexpected files in managed plugin: " + ", ".join(sorted(extras)))


def run(profile_path, output, commit, check=False):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise Invalid("source-commit must be an explicit 40-character lowercase hex foundation commit")
    profile = validate_profile(profile_path)
    files, modes = generate(profile, commit)
    validate_destination(output, profile, files)
    if check:
        mismatches = [name for name, content in files.items()
                      if not (output / name).is_file() or (output / name).read_bytes() != content
                      or file_mode(output / name) != modes[name]]
        if mismatches:
            raise Invalid("generated output or provenance differs: " + ", ".join(sorted(mismatches)))
        return
    # Validate the whole plan before writing. Atomic per-file replacement and lock
    # written last make an interrupted render detectable by the read-only check.
    for name, content in files.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".render-", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(content)
            os.chmod(temporary, int(modes[name], 8))
            os.replace(temporary, target)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-commit", required=True, help="foundation source commit, not candidate final commit")
    parser.add_argument("--check", action="store_true", help="validate complete generated tree and provenance without writes")
    args = parser.parse_args()
    try:
        run(args.profile.absolute(), args.output.absolute(), args.source_commit, args.check)
    except (Invalid, OSError, UnicodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Generated output verified." if args.check else "Generated output rendered; candidate installation and task identity remain separate checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
