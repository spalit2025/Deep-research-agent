#!/usr/bin/env python3
"""
Enhanced main entry point with template selection
"""

import argparse
import asyncio
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from config import get_config
from report_generator import ImprovedReportGenerator
from utils.observability import (
    ComponentType,
    OperationType,
    get_logger,
    get_observability_manager,
    timed_operation,
)

console = Console()

# Initialize structured logging
logger = get_logger(ComponentType.REPORT_GENERATOR)
obs = get_observability_manager()

VALID_TEMPLATES = ["standard", "business", "academic", "technical", "quick"]


def check_system_health():
    """Check system health before starting operations"""
    health = obs.get_health_status()

    logger.info(
        "System health check",
        status=health["status"],
        total_operations=health["total_operations"],
        error_rate=health["overall_error_rate"],
    )

    if health["status"] == "unhealthy":
        console.print(
            f"[bold red]⚠️ System health: {health['status'].upper()}[/bold red]"
        )
        console.print(f"[red]Error rate: {health['overall_error_rate']:.1%}[/red]")
        return False
    elif health["status"] == "degraded":
        console.print(f"[yellow]⚠️ System health: {health['status'].upper()}[/yellow]")
        console.print(
            f"[yellow]Error rate: {health['overall_error_rate']:.1%}[/yellow]"
        )
    else:
        console.print(f"[green]✅ System health: {health['status'].upper()}[/green]")

    return True


def show_template_options():
    """Display available report templates"""
    table = Table(title="📊 Available Report Templates")
    table.add_column("Template", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Best For", style="green")

    table.add_row(
        "standard",
        "Balanced research report with intro, main sections, conclusion",
        "General research, overviews",
    )
    table.add_row(
        "business",
        "Executive summary, market analysis, strategic recommendations",
        "Business analysis, market research",
    )
    table.add_row(
        "academic",
        "Abstract, literature review, analysis, conclusions",
        "Academic research, scholarly analysis",
    )
    table.add_row(
        "technical",
        "Technical overview, specifications, implementation details",
        "Technology analysis, system documentation",
    )
    table.add_row(
        "quick",
        "Shorter sections, faster generation, concise format",
        "Quick insights, rapid analysis",
    )

    console.print(table)


@timed_operation(
    "interactive_session",
    ComponentType.REPORT_GENERATOR,
    OperationType.REPORT_GENERATION,
)
async def interactive_mode():
    """Enhanced interactive mode with template selection"""

    logger.info("Starting interactive mode")

    # Check system health before starting
    if not check_system_health():
        console.print(
            "[red]System is unhealthy. Please check logs and try again.[/red]"
        )
        return

    console.print(
        Panel.fit(
            "[bold blue]🤖 Enhanced Report Generator[/bold blue]\n"
            "Generate comprehensive research reports with multiple templates",
            title="AI Report Generator v2.0",
        )
    )

    while True:
        try:
            # Show template options
            show_template_options()

            # Get template choice
            template_choice = Prompt.ask(
                "\n[cyan]Choose a template[/cyan]",
                choices=VALID_TEMPLATES,
                default="standard",
            )

            # Get topic from user
            topic = console.input(
                "\n[bold cyan]Enter your research topic: [/bold cyan]"
            )

            if not topic.strip():
                console.print("[red]Please enter a valid topic.[/red]")
                continue

            user_id = f"user_{hash(topic) % 10000}"

            logger.info(
                "Starting report generation request",
                topic=topic,
                template=template_choice,
                user_id=user_id,
            )

            console.print(
                f"\n[green]Generating {template_choice} report on: {topic}[/green]"
            )

            # Single generator instance for both generation and saving
            config = get_config(template_choice)
            generator = ImprovedReportGenerator(config)

            with console.status(f"[bold green]Generating {template_choice} report..."):
                report = await generator.generate_report(topic, user_id=user_id)

            filename = generator.save_report(report)

            # Display success message
            console.print(
                "\n[bold green]✅ Report generated successfully![/bold green]"
            )
            console.print(f"[blue]📁 Saved to: {filename}[/blue]")
            console.print(f"[yellow]📋 Template: {template_choice.title()}[/yellow]")

            # Ask if user wants to see the report
            show_report = Confirm.ask(
                "\n[cyan]Display report now?[/cyan]", default=True
            )

            if show_report:
                console.print("\n" + "=" * 80)
                markdown_report = Markdown(report)
                console.print(markdown_report)
                console.print("=" * 80)

            # Ask if user wants to generate another report
            continue_generating = Confirm.ask(
                "\n[cyan]Generate another report?[/cyan]", default=True
            )

            if not continue_generating:
                console.print(
                    "[yellow]Thanks for using the Report Generator! 👋[/yellow]"
                )
                break

        except KeyboardInterrupt:
            logger.info("Interactive session cancelled by user")
            console.print("\n\n[yellow]Operation cancelled.[/yellow]")
            break
        except Exception as e:
            logger.error(
                "Interactive session error",
                error=e,
                topic=topic if "topic" in locals() else "unknown",
                template=template_choice
                if "template_choice" in locals()
                else "unknown",
            )
            console.print(f"\n[bold red]❌ Error: {e}[/bold red]")

            # Ask if user wants to try again
            retry = Confirm.ask("[cyan]Try again?[/cyan]", default=True)
            if not retry:
                logger.info("User chose not to retry after error")
                break

    logger.info("Interactive mode session ended")


@timed_operation(
    "single_report", ComponentType.REPORT_GENERATOR, OperationType.REPORT_GENERATION
)
async def single_report_mode(topic: str, template: str = "standard"):
    """Generate a single report for the given topic"""

    user_id = f"cli_user_{hash(topic) % 10000}"

    logger.info(
        "Starting single report generation",
        topic=topic,
        template=template,
        user_id=user_id,
    )

    # Check system health
    if not check_system_health():
        console.print("[red]System is unhealthy. Aborting report generation.[/red]")
        sys.exit(1)

    console.print(f"[green]Generating {template} report on: {topic}[/green]")

    try:
        # Single generator instance for both generation and saving
        config = get_config(template)
        generator = ImprovedReportGenerator(config)

        with console.status(f"[bold green]Generating {template} report..."):
            report = await generator.generate_report(topic, user_id=user_id)

        filename = generator.save_report(report)

        console.print("\n[bold green]✅ Report generated successfully![/bold green]")
        console.print(f"[blue]📁 Saved to: {filename}[/blue]")
        console.print(f"[yellow]📋 Template: {template.title()}[/yellow]")

        # Display the report
        console.print("\n" + "=" * 80)
        markdown_report = Markdown(report)
        console.print(markdown_report)
        console.print("=" * 80)

    except Exception as e:
        logger.error(
            "Single report generation failed",
            error=e,
            topic=topic,
            template=template,
            user_id=user_id,
        )
        console.print(f"[bold red]❌ Error: {e}[/bold red]")
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser"""
    parser = argparse.ArgumentParser(
        prog="deep-research",
        description="AI-powered research report generator with multiple templates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  %(prog)s                                  Interactive mode
  %(prog)s "AI in Healthcare"               Standard report
  %(prog)s "Market Trends" -t business      Business report
  %(prog)s "Quantum Computing" -t academic  Academic report
        """,
    )
    parser.add_argument(
        "topic",
        nargs="?",
        default=None,
        help="Research topic (omit for interactive mode)",
    )
    parser.add_argument(
        "-t",
        "--template",
        choices=VALID_TEMPLATES,
        default="standard",
        help="Report template (default: standard)",
    )
    return parser


def main():
    """Main entry point with argparse-based argument parsing"""

    logger.info("Application starting")

    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.topic:
            asyncio.run(single_report_mode(args.topic, args.template))
        else:
            asyncio.run(interactive_mode())

    finally:
        # Show final system health summary
        health = obs.get_health_status()

        if health["total_operations"] > 0:
            console.print("\n[dim]📊 Session Summary:[/dim]")
            console.print(f"[dim]   Operations: {health['total_operations']}[/dim]")
            console.print(
                f"[dim]   Success Rate: {(1 - health['overall_error_rate']):.1%}[/dim]"
            )
            console.print(f"[dim]   System Health: {health['status'].upper()}[/dim]")

        logger.info(
            "Application ending",
            total_operations=health["total_operations"],
            final_health_status=health["status"],
            final_error_rate=health["overall_error_rate"],
        )


if __name__ == "__main__":
    main()
