math.randomseed(os.time())

local function strip(s)
  return s:match("^%s*(.*%S?)%s*$") or ""
end

-- Split paragraph content by SoftBreak elements into separate lines
local function split_by_softbreak(inlines)
  local lines = {}
  local current_line = pandoc.Inlines{}

  for _, inline in ipairs(inlines) do
    if inline.t == 'SoftBreak' then
      if #current_line > 0 then
        table.insert(lines, current_line)
        current_line = pandoc.Inlines{}
      end
    else
      current_line:insert(inline)
    end
  end

  if #current_line > 0 then
    table.insert(lines, current_line)
  end

  return lines
end

-- Parse a line to extract answer info
local function parse_answer_line(inlines)
  local text = pandoc.utils.stringify(inlines)
  local first_char = text:sub(1, 1)

  if first_char == '+' then
    return {text = strip(text:sub(2)), correct = true}
  elseif first_char == '-' then
    return {text = strip(text:sub(2)), correct = false}
  end

  return nil
end

function Div(el)
  if el.classes:includes('qcm') then
    local question_title = nil
    local answers = {}

    -- Iterate through the content blocks of the Div
    for _, block in ipairs(el.content) do
      if block.t == 'Header' then
        question_title = block.content
      elseif block.t == 'Para' then
        -- Split paragraph by SoftBreak to handle consecutive answer lines
        local lines = split_by_softbreak(block.content)

        for _, line_inlines in ipairs(lines) do
          local answer = parse_answer_line(line_inlines)
          if answer then
            table.insert(answers, answer)
          end
        end
      end
    end

    -- Shuffle answers using Fisher-Yates algorithm
    local shuffled_answers = {}
    local indices = {}
    for i = 1, #answers do
      indices[i] = i
    end

    for i = #indices, 2, -1 do
      local j = math.random(i)
      indices[i], indices[j] = indices[j], indices[i]
    end

    for _, idx in ipairs(indices) do
      table.insert(shuffled_answers, answers[idx])
    end

    -- Construct the output
    local list_items = {}
    local qcm_id = "qcm-" .. math.random(100000, 999999)

    for i, ans in ipairs(shuffled_answers) do
      local checkbox_id = qcm_id .. "-ans-" .. i
      local checkbox = pandoc.RawInline('html', '<input type="checkbox" id="' .. checkbox_id .. '" data-correct="' .. tostring(ans.correct) .. '">')
      local label = pandoc.RawInline('html', '<label for="' .. checkbox_id .. '">' .. ans.text .. '</label>')
      table.insert(list_items, pandoc.Plain({checkbox, pandoc.Space(), label}))
    end

    -- Get points if specified
    local points = el.attributes['points']

    -- Create question header (use level 3 to avoid section issues)
    local header_level = 3
    local title_inlines = question_title or pandoc.Inlines{}

    -- Add points if specified
    if points then
      local points_label = tonumber(points) == 1 and "point" or "points"
      title_inlines:insert(pandoc.Space())
      title_inlines:insert(pandoc.RawInline('html', '<span class="qcm-points">(' .. points .. ' ' .. points_label .. ')</span>'))
    end

    local question_block = pandoc.Header(header_level, title_inlines)

    local content_blocks = {question_block, pandoc.BulletList(list_items)}

    -- Add base styles for all qcm questions
    table.insert(content_blocks, pandoc.RawBlock('html', [[
<style>
  .qcm-question {
    margin-bottom: 1.5em;
    padding: 1em;
    border: 1px solid #ddd;
    border-radius: 5px;
  }
  .qcm-question ul {
    list-style: none;
    padding-left: 0;
  }
  .qcm-question input[type="checkbox"] {
    width: 1.2em;
    height: 1.2em;
    margin-right: 0.5em;
    vertical-align: middle;
    cursor: pointer;
  }
  .qcm-question label {
    cursor: pointer;
    vertical-align: middle;
  }
  .qcm-points {
    font-weight: normal;
    font-size: 0.85em;
    color: #666;
  }
</style>
]]))

    -- Add solution verification if enabled
    local show_solution = el.attributes['solution'] == 'true'

    if show_solution then
      table.insert(content_blocks, pandoc.RawBlock('html', '<button class="qcm-verify-button" data-qcm-id="' .. qcm_id .. '">Verify</button>'))
      table.insert(content_blocks, pandoc.RawBlock('html', [[
<style>
  .qcm-verify-button {
    margin-top: 0.5em;
    padding: 0.5em 1em;
    background-color: #007bff;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  .qcm-verify-button:hover {
    background-color: #0056b3;
  }
  .qcm-answer-correct {
    background-color: #d4edda !important;
    border-left: 3px solid #28a745;
    padding-left: 0.5em;
  }
  .qcm-answer-incorrect {
    background-color: #f8d7da !important;
    border-left: 3px solid #dc3545;
    padding-left: 0.5em;
  }
</style>
<script>
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.qcm-verify-button').forEach(button => {
    button.addEventListener('click', function() {
      const qcmId = this.getAttribute('data-qcm-id');
      const qcmDiv = document.getElementById(qcmId);
      if (!qcmDiv) return;

      qcmDiv.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
        const listItem = checkbox.closest('li');
        if (!listItem) return;

        listItem.classList.remove('qcm-answer-correct', 'qcm-answer-incorrect');

        const isCorrect = checkbox.getAttribute('data-correct') === 'true';

        if (isCorrect) {
          listItem.classList.add('qcm-answer-correct');
        } else {
          listItem.classList.add('qcm-answer-incorrect');
        }
      });
    });
  });
});
</script>
]]))
    end

    local div_attr = pandoc.Attr(qcm_id, {'qcm-question'}, {})
    return pandoc.Div(content_blocks, div_attr)
  end
  return el
end
