# Markdown Slide Master

This repository contains a template for creating slides and books using Quarto. It is designed to be used as a starting point for your own courses in HES-SO Valais-Wallis style. 

The repository includes Continous Integration (CI) configuration for automatic deployment of the book and slides to GitHub Pages.
The individual GitHub Pages should then be linked on moodle. 



#### Live preview of a single slide set
```
quarto preview Week1/slides.md
```

#### Live preview of a book
```
quarto preview --profile book
```

#### Generate book and slides locally
```
quarto render --profile book
```

