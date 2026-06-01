-- Textanswer: Create empty answer boxes for student responses

function Div(el)
  if el.classes:includes('textanswer') then
    local num_lines = tonumber(el.attributes['lines']) or 10
    local points = el.attributes['points']
    local question_title = nil
    local content_blocks = {}

    -- Extract header and other content
    local other_content = {}
    for _, block in ipairs(el.content) do
      if block.t == 'Header' then
        question_title = block.content
      else
        table.insert(other_content, block)
      end
    end

    -- Add question header with optional points
    if question_title or points then
      local header_content = pandoc.Inlines{}

      if question_title then
        header_content:extend(question_title)
      end

      if points then
        if #header_content > 0 then
          header_content:insert(pandoc.Space())
        end
        header_content:insert(pandoc.RawInline('html', '<span class="textanswer-points">(' .. points .. ' points)</span>'))
      end

      table.insert(content_blocks, pandoc.Header(3, header_content))
    end

    -- Add any other content (paragraphs, etc.) before the textarea
    for _, block in ipairs(other_content) do
      table.insert(content_blocks, block)
    end

    -- Calculate box height based on number of lines
    -- Assuming ~1.5em per line for comfortable writing
    local box_height = num_lines * 1.5

    -- Create the answer box
    local answer_box_id = "textanswer-" .. math.random(100000, 999999)

    -- Create textarea styled as an answer box
    table.insert(content_blocks, pandoc.RawBlock('html',
      '<textarea class="textanswer-box" style="height: ' .. box_height .. 'em;" placeholder="Answer..."></textarea>'
    ))

    -- Add styles
    table.insert(content_blocks, pandoc.RawBlock('html', [[
<style>

textarea::placeholder {
  opacity: 0.5;
}
  .textanswer-container {
    margin-bottom: 1.5em;
    padding: 1em;
    border: 1px solid #ddd;
    border-radius: 5px;
  }
  .textanswer-container h3 {
    margin-top: 0;
    margin-bottom: 0.5em;
  }
  .textanswer-points {
    font-weight: normal;
    font-size: 0.85em;
    color: #666;
  }
  .textanswer-box {
    width: 100%;
    border: 1px solid #ccc;
    border-radius: 3px;
    background-color: #fafafa;
    min-height: 3em;
    padding: 0.75em;
    font-family: inherit;
    font-size: inherit;
    line-height: 1.5;
    resize: vertical;
    box-sizing: border-box;
  }
  @media print {
    .textanswer-box {
      background-color: white;
      border: 1px solid #000;
    }
  }
</style>
]]))

    local div_attr = pandoc.Attr(answer_box_id, {'textanswer-container'}, {})
    return pandoc.Div(content_blocks, div_attr)
  end
  return el
end
