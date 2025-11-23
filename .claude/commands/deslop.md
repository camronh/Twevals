De-slop the changes

Slop refers to a style of coding that I do not like. The code make work, and tests may pass, but its about the style of code thats written. Your job is to review the changes and remove the slop.

The goal:
1. Simple, understandable, non-confusing code
2. No useless code
3. Efficient code, as in solves the most in the fewest lines of code

The type of slop code you might look out for:

- functions that are only used in 1 place are bad practice. The only time a short function makes sense is to keep things DRY. There are some exceptions where longer functions that are only used once make sense. I just want to avoid spaghetti code jumping all over the place. No need to make things into little reusable functions if theyre not actively being reused somewhere. 

- Overly defensive code should be removed. The authors tend to overdue the fallbacks and error handling and safety. Things like type checking things that would obviously be the correct type. Or falling back to another hardcoded value if something expected is not found. We want things to fail loudly if they arent where we expect them to be! But this is also a great opportunity to reduce lines of code. 

- Comments that refer to chronological changes of code should be removed/replaced. Sometimes you may see comments that don't explain the code, but rather explain how this code related to previous implementations. These are not useful and should be removed.

