# RexLit Frontend Prototype
## Legal Archaeology Command Center

A distinctive, production-grade interface design for RexLit that goes beyond generic terminal aesthetics to create a memorable, professional litigation workbench.

---

## Design Vision

### Conceptual Direction: "Legal Archaeology Command Center"

This isn't just another dark terminal interface - it's a **forensic workbench** where legal professionals excavate truth from document archives.

**Think:**
- Dark command center meets rare book library
- Surgical precision instruments meets judicial authority
- Terminal efficiency meets editorial sophistication

### What Makes It Unforgettable

1. **Amber Citation Glow** - Privileged documents glow with warm amber light, like redaction highlights elevated to art
2. **Document Cards as Physical Exhibits** - Each document feels like a museum catalog item with evidence tags
3. **Audit Trail as Golden Chain** - Visual metaphor for immutable, hash-chained audit events
4. **Bates Numbers as Sacred Artifacts** - Monospaced, prominent, treated like museum catalog IDs
5. **Morphing Search Modes** - Seamless transition between GUI and CLI, serving both novices and power users

---

## Color Palette

### Primary Colors
```css
--bg-primary: #0a0e14      /* Very dark blue-black */
--bg-secondary: #1a1f29    /* Dark slate */
--bg-tertiary: #242b38     /* Elevated surfaces */
--bg-elevated: #2d3548     /* Highest surfaces */
```

### Accent Colors
```css
--amber-500: #e8b76a       /* Legal authority, citations */
--cyan-500: #4fc3f7        /* Active states, technical */
--red-privilege: #ff6b6b   /* Privileged documents */
--green-production: #51cf66 /* Production documents */
--blue-responsive: #74c0fc  /* Responsive documents */
```

### Text Colors
```css
--text-primary: #e8eaed    /* Main content */
--text-secondary: #9ca3af  /* Secondary content */
--text-tertiary: #6b7280   /* Tertiary/disabled */
```

---

## Typography

### Font Stack
```css
--font-serif: 'Newsreader', Georgia, serif
--font-sans: 'Manrope', -apple-system, sans-serif
--font-mono: 'JetBrains Mono', 'Courier New', monospace
```

### Usage
- **Newsreader (Serif)**: Document titles, headings, case names - editorial gravitas
- **Manrope (Sans)**: UI elements, body text, labels - modern but not overused
- **JetBrains Mono**: Bates numbers, terminal, code, metadata - technical precision

---

## Key Components

### 1. Status Bar (Hardware LED Aesthetic)
- Amber scanline animation
- LED-style indicators with glow effects
- Case badge with serif case name
- Real-time Bates counter
- Audit chain visualization

### 2. Navigation Rail
- Icon + label vertical layout
- Amber accent border on active state
- 80px fixed width for consistency
- Bottom-aligned settings

### 3. Search Panel (GUI/CLI Toggle)
- **GUI Mode**: Traditional form with filters
- **CLI Mode**: Terminal-style command input with syntax highlighting
- Seamless toggle animation
- Command history support (up/down arrows)
- Filter pills with active states

### 4. Document Cards (Exhibition Aesthetic)
- **Bates Tag**: Museum catalog-style identification
- **Privilege Badge**: Glowing badge for privileged docs
- **Metadata Icons**: Minimal, informative
- **Excerpt Preview**: 3-line clamp
- **Tags**: Amber-accented, uppercase
- **Confidence Score**: For AI-classified documents
- **Hover State**: Amber glow for privileged, subtle shift
- **Active State**: Cyan border with shadow

### 5. Document Viewer
- **Breadcrumb Navigation**: Current location
- **Action Toolbar**: Download, Annotate, Redact
- **Metadata Panel**: Left sidebar with:
  - Document information grid
  - Classification status (with icon)
  - Audit timeline (chain aesthetic)
- **Document Preview**: Center, simulated email rendering
- **Privilege Highlights**: Amber glow on sensitive content

### 6. Audit Timeline (Chain Aesthetic)
- Vertical timeline with connecting line
- Dots transition from gray → amber (active)
- Gold gradient line suggesting hash chain
- Monospaced timestamps
- Active event pulses

---

## Animations & Micro-interactions

### Staggered Entry
```css
.document-card:nth-child(1) { animation-delay: 0ms; }
.document-card:nth-child(2) { animation-delay: 50ms; }
.document-card:nth-child(3) { animation-delay: 100ms; }
```

### Amber Glow (Privileged Documents)
```css
@keyframes amberPulse {
    0%, 100% { box-shadow: 0 0 12px rgba(255, 107, 107, 0.4); }
    50% { box-shadow: 0 0 20px rgba(255, 107, 107, 0.6); }
}
```

### LED Pulse (Status Indicators)
```css
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}
```

### Scanline (Status Bar)
```css
@keyframes scanline {
    from { transform: translateX(-100%); }
    to { transform: translateX(100%); }
}
```

### Document Transition
- Fade + subtle translateY on switch
- 300ms cubic-bezier easing
- Smooth, not jarring

---

## Keyboard Shortcuts

### Navigation
- `⌘/Ctrl + K` - Focus search
- `⌘/Ctrl + /` - Toggle GUI/CLI mode
- `⌘/Ctrl + P` - Command palette (future)
- `?` - Show keyboard shortcuts overlay
- `Esc` - Close overlays
- `J/K` - Navigate documents (Vim-style)

### Document Actions
- `⌘/Ctrl + D` - Download
- `⌘/Ctrl + A` - Annotate
- `⌘/Ctrl + R` - Redact

### Classification
- `P` - Mark privileged
- `R` - Mark responsive
- `X` - Mark for production

### CLI Mode
- `↑/↓` - Command history
- `Enter` - Execute command

---

## Effects & Details

### Custom Scrollbar
- Dark track with border
- Elevated thumb with hover state
- Borderless, industrial aesthetic

### Selection
- Amber background (`#e8b76a`)
- Dark text for readability

### Shadows
```css
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3)
--shadow-md: 0 4px 6px rgba(0, 0, 0, 0.4)
--shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.5)
--shadow-amber-glow: 0 0 20px rgba(232, 183, 106, 0.3)
--shadow-cyan-glow: 0 0 15px rgba(79, 195, 247, 0.4)
```

### Toast Notifications
- Fixed bottom-right
- Amber border with glow
- Monospaced uppercase text
- Slide in/out animations
- Auto-dismiss after 2s

---

## Implementation Notes

### Browser Support
- Modern evergreen browsers (Chrome, Firefox, Safari, Edge)
- CSS Grid for layouts
- CSS Custom Properties (variables)
- No IE11 support needed

### Performance
- CSS-only animations where possible
- Minimal JavaScript overhead
- Lazy loading for document content
- Virtual scrolling for large document lists

### Accessibility
- Keyboard navigation throughout
- ARIA labels on interactive elements
- Focus visible styles
- Color contrast meets WCAG AA
- Screen reader friendly

### Responsive Breakpoints
- **1200px**: Narrower search panel (400px → 350px)
- **900px**: Hide metadata panel, single-column viewer
- Mobile-first principles for smaller screens

---

## How to View

1. Open `index.html` in a modern browser
2. Press `?` to see keyboard shortcuts
3. Try toggling GUI/CLI mode with the switch
4. Click document cards to switch active document
5. Use `J/K` keys to navigate documents Vim-style
6. Try classification shortcuts: `P`, `R`, `X`

---

## Design Principles

### 5 Questions to Guide All Decisions:
1. **Does this look like it was built for litigation work?**
2. **Would a legal professional trust this tool with privileged documents?**
3. **Does the UI emphasize offline-first and audit trail?**
4. **Is this visually distinct from Relativity/Everlaw/generic SaaS?**
5. **Does every interaction feel intentional and professional?**

### Guardrails
- **No purple gradients** (cliché AI aesthetic)
- **No Inter/Roboto** (overused SaaS fonts)
- **No overly playful animations** (this is legal work)
- **No pure white backgrounds** (harsh, unprofessional for long reading)
- **No generic blue (#2563eb)** (already replaced with amber/cyan)

---

## Future Enhancements

### Phase 1 (Current Prototype)
- ✅ Core layout and navigation
- ✅ Search GUI/CLI modes
- ✅ Document cards with classification
- ✅ Document viewer with metadata
- ✅ Audit timeline visualization
- ✅ Keyboard shortcuts

### Phase 2 (Next Steps)
- [ ] Real document loading
- [ ] Redaction UI with amber overlays
- [ ] Annotation toolkit
- [ ] Export workflows
- [ ] Advanced search syntax highlighting
- [ ] Command palette (`⌘K`)

### Phase 3 (Advanced)
- [ ] Offline indicator with sync status
- [ ] Collaborative review features
- [ ] Batch operations UI
- [ ] Production set management
- [ ] Privilege log generation
- [ ] Analytics dashboard

---

## Credits

**Design System**: Legal Archaeology Command Center
**Aesthetic Direction**: Terminal-adjacent forensic workbench
**Color Philosophy**: Amber authority, cyan precision, dark professionalism
**Typography**: Editorial serif × modern sans × technical mono

**Inspiration**:
- Judicial chambers (authority, gravitas)
- Rare book archives (preservation, care)
- Command centers (precision, control)
- Surgical theaters (clean, focused)
- Art deco terminals (geometric, refined)

---

## License

Part of the RexLit project. See main repository for license details.

---

**Built with Claude Code** 🎨
