Clean up the EZVals Codebase

I want to clean up tech debt and remove as many lines of code as possible in this codebase. The goal is to simplify the codebase as much as possible while still maintaining the same behavior and performance. The ultimate flex of a good developer is to tell them to download my lib, and its this many lines of code! The behavior right now is great, I just want to simplify the code. I suggest you:

1. Make sure integration tests give you a snapshot of the current public behavior. Crosscheck the @CHANGELOG.md and @README.md to make sure all public features and edge cases mentioned are covered in the integration tests.
2. Remove the bloat code
3. Run tests to confirm no regressions. 

The goal:
1. Simple, understandable, non-confusing code
2. No useless code
3. Efficient code, as in solves the most in the fewest lines of code

The type of bloat code you might look out for:
- functions that are only used in 1 place are bad practice. The only time a short function makes sense is to keep things DRY. There are some exceptions where longer functions that are only used once make sense. I just want to avoid spaghetti code jumping all over the place. No need to make things into little reusable functions if theyre not actively being reused somewhere. 

- Overly defensive code should be removed. The authors tend to overdue the fallbacks and error handling and safety. Things like type checking things that would obviously be the correct type. Or falling back to another hardcoded value if something expected is not found. We want things to fail loudly if they arent where we expect them to be! But this is also a great opportunity to reduce lines of code. 


Besides that, you have carte blanche. Comments and clear naming is useful for maintainablilty 