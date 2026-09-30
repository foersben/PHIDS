🎯 **What:** The database save and rebuild endpoints were catching `Exception` and returning the raw string representation (and stderr) directly in the HTTP response.

⚠️ **Risk:** This is an information exposure vulnerability (CWE-209: Generation of Error Message Containing Sensitive Information). It can leak file paths, system commands, or stack traces if the exception is deep enough, giving attackers insights into the system's internals.

🛡️ **Solution:** Modified the endpoints to log the exception internally using a module-level logger, and return a generic error message (`Failed to save database`, `ETL Failed`) to the user. Added comprehensive unit tests to ensure exception strings are no longer leaked in the response bodies.
