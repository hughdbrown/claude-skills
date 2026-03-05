In the directory `splitpr_05`, create a python3 script (using `uv`) that takes a sqlite3 database created by `splitpr_00` and
  converts that into a series of PRs and implements the code changes designed by the sqlite3 database in the previous script.
  - it needs `click` for command line arguments
  - it needs `anthropic` for AI provider operations
  There are some files to use and extend for utility function:
  - db.py for database operations
  - git_ops.py for manipulating git
  Execution of the script should work the same as for splitpr_00, including using `uv` to create temporary virtualenvs for
  third-party libraries.

  The script needs command line options for:
  - selecting database
  - doing dry-run of repo operations (including not actually creating pull requests, not modifying files with cherry-picks, not
  creating git branches< and so on). A dry-run should print out commands or operations it would execute but not actually do them.

  The idea is that calling splitpr_00 sets up the plan and calling splitpr_05 executes the plan that would restructure the mega-PR
  into several smaller and more coherent PRs.

  For an understanding of the complete tool that these scripts implement, see the description of the skill in
  `~/workspace/hughdbrown/claude-skills/hdb-split-pr/SKILL.md`.
