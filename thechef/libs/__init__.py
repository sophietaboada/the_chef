"""Generic building blocks with no domain knowledge.

Rule: modules in libs/ never import from the domain packages (accounts, foods, recipes, ...).
Domains depend on libs, never the other way round.
"""
