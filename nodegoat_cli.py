#!/usr/bin/env python3
"""
CLI tool for exploring nodegoat data structure.

Usage:
  uv run nodegoat_cli.py list-types [--project PROJECT_ID]
  uv run nodegoat_cli.py show-type TYPE_ID [--project PROJECT_ID]
  uv run nodegoat_cli.py query-objects TYPE_ID [--limit N] [--search TERM] [--project PROJECT_ID]
  uv run nodegoat_cli.py get-object TYPE_ID OBJECT_ID [--project PROJECT_ID]
  uv run nodegoat_cli.py openapi [--project PROJECT_ID]

Examples:
  # List all Object Types in your project
  uv run nodegoat_cli.py list-types

  # Show structure of a specific Type
  uv run nodegoat_cli.py show-type 123

  # Query objects of a Type (with search)
  uv run nodegoat_cli.py query-objects 123 --limit 5 --search "Athens"

  # Get a specific object
  uv run nodegoat_cli.py get-object 123 456
"""
import argparse
import json
import sys
from nodegoat_client import NodegoatClient


def print_json(data):
    """Pretty-print JSON data."""
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_list_types(client, args):
    """List all Object Types."""
    print("Fetching Object Types...")
    result = client.query_model(project_id=args.project)

    if "data" in result:
        types = result["data"]
        print(f"\nFound {len(types)} Object Type(s):\n")
        for type_id, type_data in types.items():
            name = type_data.get("name", "Unknown")
            print(f"  ID {type_id}: {name}")
            if "object_name_options" in type_data:
                print(f"    Object name: {type_data['object_name_options']}")
    else:
        print("\nRaw response:")
        print_json(result)


def cmd_show_type(client, args):
    """Show structure of a specific Type."""
    print(f"Fetching Type {args.type_id} structure...")
    result = client.query_model(type_id=args.type_id, project_id=args.project)

    if "data" in result:
        type_data = result["data"]
        print(f"\nType: {type_data.get('name', 'Unknown')}\n")

        # Show object name configuration
        if "object_name_options" in type_data:
            print("Object Name Configuration:")
            print_json(type_data["object_name_options"])
            print()

        # Show object descriptions (fields)
        if "object_descriptions" in type_data:
            print("Object Descriptions (Fields):")
            for desc_id, desc_data in type_data["object_descriptions"].items():
                print(f"  ID {desc_id}: {desc_data.get('name', 'Unknown')}")
                print(f"    Type: {desc_data.get('value_type_base', 'unknown')}")
                if desc_data.get("is_required"):
                    print("    Required: Yes")
            print()

        # Show sub-objects
        if "object_sub_details" in type_data:
            print("Sub-Objects:")
            for sub_id, sub_data in type_data["object_sub_details"].items():
                print(f"  ID {sub_id}: {sub_data.get('name', 'Unknown')}")
            print()
    else:
        print("\nRaw response:")
        print_json(result)


def cmd_query_objects(client, args):
    """Query objects of a Type."""
    print(f"Querying Type {args.type_id} objects...")
    if args.search:
        print(f"  Search: {args.search}")
    if args.limit:
        print(f"  Limit: {args.limit}")

    result = client.query_data(
        type_id=args.type_id,
        project_id=args.project,
        search=args.search,
        limit=args.limit,
    )

    if "data" in result:
        objects = result["data"]
        print(f"\nFound {len(objects)} object(s):\n")

        for obj_id, obj_data in list(objects.items())[:args.limit or 999]:
            # Show object name
            if "object" in obj_data:
                name = obj_data["object"].get("object_name_plain", "Unnamed")
                print(f"ID {obj_id}: {name}")

            # Show first few fields
            if "object_definitions" in obj_data:
                for desc_id, desc_value in list(obj_data["object_definitions"].items())[:3]:
                    if desc_value:
                        # Handle both simple values and complex objects
                        if isinstance(desc_value, dict):
                            val = desc_value.get("value", str(desc_value))
                        else:
                            val = desc_value
                        # Truncate long values
                        val_str = str(val)[:100]
                        if len(str(val)) > 100:
                            val_str += "..."
                        print(f"  Field {desc_id}: {val_str}")
            print()
    else:
        print("\nRaw response:")
        print_json(result)


def cmd_get_object(client, args):
    """Get a specific object by ID."""
    print(f"Fetching object {args.object_id} from Type {args.type_id}...")

    result = client.query_data(
        type_id=args.type_id,
        object_id=args.object_id,
        project_id=args.project,
    )

    print("\nObject data:")
    print_json(result)


def cmd_openapi(client, args):
    """Get OpenAPI specification."""
    print("Fetching OpenAPI specification...")
    result = client.get_openapi_spec(project_id=args.project)
    print_json(result)


def main():
    parser = argparse.ArgumentParser(
        description="Explore nodegoat data structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # list-types command
    list_parser = subparsers.add_parser("list-types", help="List all Object Types")
    list_parser.add_argument("--project", help="Project ID (default: from config)")

    # show-type command
    show_parser = subparsers.add_parser("show-type", help="Show Type structure")
    show_parser.add_argument("type_id", type=int, help="Type ID to inspect")
    show_parser.add_argument("--project", help="Project ID (default: from config)")

    # query-objects command
    query_parser = subparsers.add_parser("query-objects", help="Query objects")
    query_parser.add_argument("type_id", type=int, help="Type ID to query")
    query_parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    query_parser.add_argument("--search", help="Search term")
    query_parser.add_argument("--project", help="Project ID (default: from config)")

    # get-object command
    get_parser = subparsers.add_parser("get-object", help="Get specific object")
    get_parser.add_argument("type_id", type=int, help="Type ID")
    get_parser.add_argument("object_id", type=int, help="Object ID")
    get_parser.add_argument("--project", help="Project ID (default: from config)")

    # openapi command
    openapi_parser = subparsers.add_parser("openapi", help="Get OpenAPI spec")
    openapi_parser.add_argument("--project", help="Project ID (default: from config)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        client = NodegoatClient()

        commands = {
            "list-types": cmd_list_types,
            "show-type": cmd_show_type,
            "query-objects": cmd_query_objects,
            "get-object": cmd_get_object,
            "openapi": cmd_openapi,
        }

        commands[args.command](client, args)

    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print("\nMake sure you have:", file=sys.stderr)
        print("1. Copied stephanos.ini.example to stephanos.ini", file=sys.stderr)
        print("2. Added your nodegoat token to stephanos.ini", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
