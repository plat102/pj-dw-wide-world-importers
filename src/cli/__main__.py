"""`python -m cli`, for when the installed `wwi` script is not on PATH."""

from cli.app import main

raise SystemExit(main())
