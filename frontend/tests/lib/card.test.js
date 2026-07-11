// Card: plain surface — children render, hover is opt-in, attrs pass through.
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/svelte'
import { createRawSnippet } from 'svelte'
import Card from '../../src/lib/Card.svelte'

const children = createRawSnippet(() => ({ render: () => '<p>card content</p>' }))

describe('Card', () => {
  it('renders children inside the surface', () => {
    render(Card, { props: { children } })
    const card = document.querySelector('.kit-card')
    expect(card).toBeTruthy()
    expect(screen.getByText('card content')).toBeInTheDocument()
  })

  it('hover class is opt-in', () => {
    render(Card, { props: { children, hover: true } })
    expect(document.querySelector('.kit-card.hover')).toBeTruthy()
  })

  it('passes extra attributes and classes through', () => {
    render(Card, { props: { children, class: 'home-card', 'data-testid': 'c' } })
    expect(screen.getByTestId('c')).toHaveClass('kit-card', 'home-card')
  })
})
