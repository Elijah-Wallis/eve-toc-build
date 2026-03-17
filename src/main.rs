use clap::{Parser, Subcommand};

mod runtime_config;

#[derive(Parser, Debug)]
#[command(name = "eve-toc-build")]
#[command(about = "Rust tooling for runtime operations", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Validate runtime config and emit a JSON report.
    ValidateRuntimeConfig,
}

fn main() {
    let cli = Cli::parse();
    let exit_code = match cli.command {
        Commands::ValidateRuntimeConfig => runtime_config::validate_runtime_config(),
    };
    std::process::exit(exit_code);
}
