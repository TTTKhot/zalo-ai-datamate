"""sqlvote - an independent route for DataMate: runtime rulebook + cleaned raw tables in DuckDB
-> K SQL drafts -> execute -> vote the way the scorer compares -> answer / unanswerable / abstain.

Nothing here is keyed on a question id or a business id. The rulebook, README and calendar are read
from the split being answered at run time.
"""
__version__ = '0.1.0'
