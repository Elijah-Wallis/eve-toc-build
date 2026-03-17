use serde::Serialize;
use serde_json::{Map, Value};
use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

const ENV_ALIASES: [(&str, &[&str]); 4] = [
    ("ANTHROPIC_API_KEY", &["ANTHORPIC_API_KEY"]),
    (
        "OPENCLAW_TELEGRAM_BOT_TOKEN",
        &["OPENCLAW_BOT_TOKEN", "TELEGRAM_BOT_TOKEN"],
    ),
    ("OPENCLAW_TELEGRAM_USER_ID", &["MY_TELEGRAM_ID"]),
    ("N8N_MCP_TOKEN", &["N8N_MCP_ACCESS_TOKEN"]),
];

#[derive(Serialize)]
struct EnvCoverage {
    set: bool,
    aliases_present: Vec<String>,
}

#[derive(Serialize)]
struct Report {
    ok: bool,
    config_path: String,
    state_dir: String,
    command_queue_file: Option<String>,
    applied_aliases: BTreeMap<String, String>,
    env_coverage: BTreeMap<String, EnvCoverage>,
    warnings: Vec<String>,
}

pub fn validate_runtime_config() -> i32 {
    let config_path = default_config_path();
    let config = load_runtime_config(&config_path);
    let aliases = apply_env_aliases();
    let queue_file = resolve_command_queue_file(&config_path, &config);
    let state_dir = resolve_state_dir();

    let mut warnings = Vec::new();
    if config.is_none() {
        warnings.push("config_unreadable_or_missing".to_string());
    }

    match &queue_file {
        None => warnings.push("missing_command_queue_path".to_string()),
        Some(path) if !path.is_absolute() => {
            warnings.push("command_queue_not_absolute".to_string())
        }
        _ => {}
    }

    if !state_dir.exists() {
        warnings.push("state_dir_missing".to_string());
    }

    let mut env_coverage = BTreeMap::new();
    for (canonical, alias_list) in ENV_ALIASES {
        let aliases_present = alias_list
            .iter()
            .filter_map(|alias| env::var(alias).ok().map(|_| (*alias).to_string()))
            .collect::<Vec<_>>();
        env_coverage.insert(
            canonical.to_string(),
            EnvCoverage {
                set: env::var(canonical).is_ok(),
                aliases_present,
            },
        );
    }

    let report = Report {
        ok: warnings.is_empty(),
        config_path: config_path.display().to_string(),
        state_dir: state_dir.display().to_string(),
        command_queue_file: queue_file.map(|p| p.display().to_string()),
        applied_aliases: aliases,
        env_coverage,
        warnings,
    };

    println!(
        "{}",
        serde_json::to_string_pretty(&report).expect("failed to serialize report")
    );

    if report.ok {
        0
    } else {
        2
    }
}

fn apply_env_aliases() -> BTreeMap<String, String> {
    let mut applied = BTreeMap::new();
    for (canonical, aliases) in ENV_ALIASES {
        if env::var(canonical).is_ok() {
            continue;
        }

        for alias in aliases {
            if let Ok(value) = env::var(alias) {
                // SAFETY: setting process env vars is expected behavior in this utility.
                unsafe {
                    env::set_var(canonical, value);
                }
                applied.insert(canonical.to_string(), alias.to_string());
                break;
            }
        }
    }
    applied
}

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn resolve_state_dir() -> PathBuf {
    if let Ok(raw) = env::var("OPENCLAW_STATE_DIR") {
        return expand_path(&raw);
    }

    if let Ok(home) = env::var("HOME") {
        return PathBuf::from(home).join(".openclaw");
    }

    repo_root().join(".openclaw")
}

fn resolve_runtime_dir() -> PathBuf {
    resolve_state_dir().join("runtime")
}

fn default_config_path() -> PathBuf {
    if let Ok(config_path) = env::var("OPENCLAW_CONFIG_PATH") {
        return expand_path(&config_path);
    }
    repo_root().join("openclaw.json")
}

fn load_runtime_config(config_path: &Path) -> Option<Value> {
    let contents = fs::read_to_string(config_path).ok()?;
    let parsed = serde_json::from_str::<Value>(&contents).ok()?;
    adapt_legacy_config(parsed, config_path)
}

fn adapt_legacy_config(config: Value, config_path: &Path) -> Option<Value> {
    let mut root = config.as_object()?.clone();

    if let Some(paths) = root.get("paths").and_then(|v| v.as_object()) {
        let mut normalized = Map::new();
        for (key, value) in paths {
            normalized.insert(key.clone(), normalize_path(value, config_path));
        }
        if !normalized.is_empty() {
            root.insert("paths".to_string(), Value::Object(normalized));
        }
    }

    Some(Value::Object(root))
}

fn normalize_path(value: &Value, config_path: &Path) -> Value {
    let Some(raw) = value.as_str() else {
        return value.clone();
    };

    let replaced = raw
        .replace("${REPO_ROOT}", &repo_root().display().to_string())
        .replace(
            "${OPENCLAW_STATE_DIR}",
            &resolve_state_dir().display().to_string(),
        );

    let expanded = expand_path(&replaced);
    if expanded.is_absolute() {
        return Value::String(expanded.display().to_string());
    }

    Value::String(
        config_path
            .parent()
            .unwrap_or_else(|| Path::new("."))
            .join(expanded)
            .display()
            .to_string(),
    )
}

fn resolve_command_queue_file(config_path: &Path, config: &Option<Value>) -> Option<PathBuf> {
    if let Some(paths_obj) = config
        .as_ref()
        .and_then(|v| v.as_object())
        .and_then(|obj| obj.get("paths"))
        .and_then(|v| v.as_object())
    {
        if let Some(queue) = paths_obj.get("commandQueueFile").and_then(|v| v.as_str()) {
            return Some(PathBuf::from(queue));
        }
    }

    if let Ok(fallback) = env::var("OPENCLAW_COMMAND_QUEUE_FILE") {
        return Some(expand_path(&fallback));
    }

    let _ = config_path; // maintain parity with existing utility signature semantics.
    Some(resolve_runtime_dir().join("command_queue.txt"))
}

fn expand_path(input: &str) -> PathBuf {
    if let Some(stripped) = input.strip_prefix("~/") {
        if let Ok(home) = env::var("HOME") {
            return PathBuf::from(home).join(stripped);
        }
    }
    PathBuf::from(input)
}
