# Issues

## Add footer

Add a footer to the bottom of the UI that links to the Github and to the Mintlify documentation.

## Fix Github URL

The correct github url is https://github.com/camronh/Twevals fix the in the docs and anywhere else its mentioned

## Trace link

Add a trace_url: string field to the ctx.run_data as ctx.run_data.trace_url = "www.google.com". Then we can make it a link in the details view in a sexy way.

## Flicker

The UI flickers while its in progress of running the evals!! its very ugly and noticeable! It needs to be smoother.

## Timeout is not being reset

If I set the timeout to empty in the UI settings, it should be set to None, but its not taking any effect and just persists as what it was before.

## Copy run command

Need to add a copy button to the run details view that copies the twevals run command to the clipboard so you can easily run it in headless mode to pass it to your agent if you want to. Should only show up on hover.

## Copy error trace

If theres an error, we show a nice red error card in the details view, which I love. But you should be able to copy the error trace to your clipboard. Should only show up on hover.

## More nouns and adjectives

We need more nouns and adjectives in the list used to generate the friendly names. Starting to feel overlap.

## Skip save command

Some kind of command to add to the run command that skips saving the results to a run file. 

## Hide api logs

When running the serve command, we dont need all the uvicorn logs. The user doesnt care about the api, they would mainly care about the live stdout logs from the running evals.

## Dataset and label filters in ui

Need an intuitive way to filter by datasets and labels in the UI. Its not possible right now.

## Shift click checks

In the UI, you should be able to click a checkbox and then hold shift another box to check all the boxes in between.

## Scoring notes missing

The score notes are not visible on the UI. They should be visible in the details view in a sexy way.

## Output under reference in ui

In the details view, the output box should be below the reference box if its present. So:

|Input | Reference|
|     Output      |

## Error shouldn’t be output in the details view

In the tables view we fallback to the error message if output is not present. But in the details view we shouldnt fall back. Output should be output, or blank if its not present.

## Need floating table headers

I want to be able to see the column names even when I scroll down.