import { useRef, useState, type ReactNode } from 'react'
import { Autocomplete, TextField, Button, Box, ButtonBase, Paper, type PaperProps } from '@mui/material'
import { fetchExplore, fetchMatchedAliases, fetchSuggestions, suggestionsNow, type ExploreNode } from '../api'
import { useGame } from '../sizes'
import { displayName } from '../names'
import { withArticle } from '../words'
import { BULK_CAP, bulkMatches, isBulkQuery, type BulkScope } from '../endgame'

/** The row heading the suggestions once bulk guessing has unlocked: every
 *  leaf in the reached group named with the typed word. See endgame.ts. */
interface BulkOption {
  kind: 'bulk'
  word: string
  names: string[]
  clade: string
}

interface Props {
  onGuess: (label: string) => void
  /** Guess several names at once. No bulk row is offered without it. */
  onBulkGuess?: (labels: string[]) => void
  /** Where a bulk guess may reach; null while it is locked. */
  bulk?: BulkScope | null
  /** What a leaf is called, for the field's label: "Guess a field". */
  noun?: string
  disabled: boolean
  exclude?: string[]
}

/** How many suggestions to ask for. TaxoQuiz had 30, in tree order, and on its
 *  41k-species dataset "cat" put the domestic cat 128th; ranking is the fix
 *  (exact, then whole word — see matchTier), and a longer list helps a word
 *  with many whole-word matches. */
const SUGGESTIONS = 50

/** The suggestions' paper with the bulk row on top. A header rather than an
 *  option: see the note on the bulk row below. */
function SuggestionsPaper({ header, children, ...rest }: PaperProps & { header?: ReactNode }) {
  return <Paper {...rest}>{header}{children}</Paper>
}

function leafLabels(node: ExploreNode, out: string[] = []): string[] {
  if (node.child_count === 0) out.push(node.label)
  for (const child of node.children) leafLabels(child, out)
  return out
}

export default function GuessInput({ onGuess, onBulkGuess, bulk, disabled, exclude = [], noun = 'answer' }: Props) {
  const [options, setOptions] = useState<string[]>([])
  // Beside a suggestion its name does not explain, the alias that found it.
  const [why, setWhy] = useState<Map<string, string>>(new Map())
  const [value, setValue] = useState<string | null>(null)
  const [inputValue, setInputValue] = useState('')
  const [open, setOpen] = useState(false)
  // The bulk row on offer for what is typed, and the one chosen, if any. Kept
  // out of the Autocomplete's options and value — see the bulk row below.
  const [offer, setOffer] = useState<BulkOption | null>(null)
  const [chosen, setChosen] = useState<BulkOption | null>(null)
  const dataset = useGame()
  // The leaves under a group, fetched once per group rather than per keystroke.
  // A group can run to a few thousand names; the cap applies after.
  const groups = useRef(new Map<string, Promise<string[]>>())
  // What was last typed, so an answer that comes back late for an earlier
  // keystroke is dropped.
  const latest = useRef('')

  function namesUnder(group: string): Promise<string[]> {
    const key = `${dataset}\u0000${group}`
    let pending = groups.current.get(key)
    if (!pending) {
      pending = fetchExplore(dataset, group, -1).then((tree) => leafLabels(tree))
      pending.catch(() => groups.current.delete(key))   // a failure is retried, not kept
      groups.current.set(key, pending)
    }
    return pending
  }

  async function handleInputChange(_: unknown, newInput: string, reason: string) {
    setInputValue(newInput)
    // Typing again un-chooses the bulk row; the reset MUI does on its own
    // after a choice does not.
    if (reason !== 'input') return
    setChosen(null)
    const query = newInput.trim()
    latest.current = query
    if (query.length < 2) {
      setOptions([])
      setOffer(null)
      return
    }
    // The list changes in the same render as the text when it can. MUI keeps
    // its highlight on an option that is still there when the list changes
    // under the same text, so a list one render late kept whatever led the
    // last one: "ros" led with the guelder rose, and Enter on "rose" guessed
    // it. Only before the tree has loaded does the list come a render late.
    const now = suggestionsNow(dataset, query, SUGGESTIONS, exclude)
    if (now) {
      setOptions(now.labels)
      setWhy(now.aliases)
    } else {
      const results = await fetchSuggestions(dataset, query, SUGGESTIONS, exclude)
      const aliases = await fetchMatchedAliases(dataset, query, results)
      if (latest.current !== query) return
      setOptions(results)
      setWhy(aliases)
    }
    let next: BulkOption | null = null
    if (bulk && onBulkGuess && isBulkQuery(query)) {
      try {
        const names = bulkMatches(await namesUnder(bulk.name), query, exclude)
        // One match is an ordinary guess, already in the list below it.
        if (names.length > 1) next = { kind: 'bulk', word: query, names, clade: bulk.label }
      } catch {
        // The ordinary suggestions still stand without the bulk row.
      }
    }
    if (latest.current === query) setOffer(next)
  }

  function bulkLabel(option: BulkOption): string {
    const count = option.names.length
    return count > BULK_CAP
      ? `${count} named "${option.word}" in ${option.clade} — too many at once (max ${BULK_CAP})`
      : `Guess all ${count} named "${option.word}" in ${option.clade}`
  }

  const tooMany = (option: BulkOption | null) => option !== null && option.names.length > BULK_CAP

  function chooseBulk(option: BulkOption) {
    setChosen(option)
    setValue(null)
    setInputValue(bulkLabel(option))
    setOpen(false)
  }

  function handleSubmit() {
    if (chosen) {
      if (!tooMany(chosen)) onBulkGuess?.(chosen.names)
    } else {
      const trimmed = (value ?? '').trim()
      if (!trimmed) return
      onGuess(trimmed)
    }
    setValue(null)
    setChosen(null)
    setOffer(null)
    setInputValue('')
    setOptions([])
  }

  // The bulk row heads the list, so it is the first thing seen once a bulk
  // guess is possible (it was the last row, below up to 50 names, and easy to
  // miss). It is a header and not an option because the list highlights its
  // first option and Enter, or tapping away, takes the highlighted one: as the
  // first option, typing "lion" and pressing Enter would have guessed every
  // lion in the group, up to a hundred guesses on the score. Choosing it still
  // only arms the Guess button, as before.
  const header = offer && (
    <ButtonBase
      component="div"
      role="button"
      aria-disabled={tooMany(offer)}
      disabled={tooMany(offer)}
      // mousedown, not click: the input must keep focus, or the list closes
      // and takes the row with it before the click lands.
      onMouseDown={(e) => {
        e.preventDefault()
        if (!tooMany(offer)) chooseBulk(offer)
      }}
      sx={{
        display: 'block', width: '100%', textAlign: 'left',
        px: 2, py: 1.25, fontWeight: 600, fontSize: '0.9rem',
        color: tooMany(offer) ? 'text.disabled' : 'primary.contrastText',
        bgcolor: tooMany(offer) ? 'action.disabledBackground' : 'primary.main',
        '&:hover': { bgcolor: tooMany(offer) ? undefined : 'primary.dark' },
      }}
    >
      {bulkLabel(offer)}
    </ButtonBase>
  )

  return (
    <Box sx={{ display: 'flex', gap: 1, width: '100%' }}>
      <Autocomplete<string, false, false, false>
        options={options}
        value={value}
        inputValue={inputValue}
        onInputChange={handleInputChange}
        onChange={(_, newValue) => { setValue(newValue); setChosen(null) }}
        open={open && (options.length > 0 || offer !== null)}
        onOpen={() => setOpen(true)}
        onClose={() => setOpen(false)}
        filterOptions={(x) => x}
        // Display only. The option *value* stays the dataset's own label, which
        // is what gets submitted — the engine matches a guess exactly and
        // answers "Not in this dataset: 'Lion'" otherwise.
        getOptionLabel={displayName}
        renderOption={({ key, ...props }, option) => (
          <li key={key} {...props}>
            {displayName(option)}
            {why.has(option) && (
              <Box component="span" sx={{ ml: 1, color: 'text.secondary', fontSize: '0.85em' }}>
                {why.get(option)}
              </Box>
            )}
          </li>
        )}
        isOptionEqualToValue={(a, b) => a === b}
        disabled={disabled}
        autoHighlight
        autoSelect
        // A chosen bulk row is not the value, so blurring to press Guess must
        // not clear the text that says what is about to be guessed.
        clearOnBlur={!chosen}
        slots={{ paper: SuggestionsPaper }}
        slotProps={{ paper: { header } as PaperProps }}
        sx={{ width: { xs: '100%', sm: 420 }, flex: { xs: 1, sm: 'none' } }}
        renderInput={(params) => (
          <TextField {...params} label={`Guess ${withArticle(noun)}`} size="small" />
        )}
      />
      <Button
        variant="contained"
        onClick={handleSubmit}
        disabled={disabled || (chosen ? tooMany(chosen) : !value)}
        sx={{ whiteSpace: 'nowrap' }}
      >
        {chosen ? `Guess all ${chosen.names.length}` : 'Guess'}
      </Button>
    </Box>
  )
}
