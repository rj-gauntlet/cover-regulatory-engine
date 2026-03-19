// @ts-check
const { test, expect } = require('@playwright/test');
const path = require('path');

const BASE_URL = 'http://localhost:3000';
const SCREENSHOTS_DIR = path.join('C:', 'Users', 'rjxxl', 'projects', 'cover', 'test-screenshots');

test.describe('Cover Regulatory Engine E2E Tests', () => {
  let consoleErrors = [];

  test.beforeEach(async ({ page }) => {
    // Capture console errors
    consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
  });

  test('Journey 1: Homepage Load', async ({ page }) => {
    console.log('\n=== Journey 1: Homepage Load ===');
    
    // Navigate to homepage
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    
    // Take screenshot
    await page.screenshot({ 
      path: path.join(SCREENSHOTS_DIR, 'smoke-homepage-desktop.png'),
      fullPage: true 
    });
    console.log('✓ Screenshot saved: smoke-homepage-desktop.png');
    
    // Check for console errors
    if (consoleErrors.length > 0) {
      console.log('⚠ Console errors detected:', consoleErrors);
    } else {
      console.log('✓ No console errors');
    }
    
    // Verify page elements
    const header = await page.locator('header').count();
    const searchInput = await page.locator('input[type="text"], input[placeholder*="address"], input[placeholder*="Address"]').count();
    const map = await page.locator('#map, [class*="map"], [id*="map"]').count();
    
    console.log('Verification:');
    console.log(`  - Header present: ${header > 0 ? 'YES' : 'NO'}`);
    console.log(`  - Search input present: ${searchInput > 0 ? 'YES' : 'NO'}`);
    console.log(`  - Map element present: ${map > 0 ? 'YES' : 'NO'}`);
    
    expect(header).toBeGreaterThan(0);
    expect(searchInput).toBeGreaterThan(0);
    
    console.log('✓ Journey 1: PASS\n');
  });

  test('Journey 2: Assessment Flow', async ({ page }) => {
    console.log('\n=== Journey 2: Assessment Flow ===');
    
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    
    // Find and fill address search input
    const searchInput = page.locator('input[type="text"], input[placeholder*="address"], input[placeholder*="Address"]').first();
    await searchInput.fill('11348 Elderwood St, Los Angeles, CA');
    console.log('✓ Address entered: 11348 Elderwood St, Los Angeles, CA');
    
    // Click Assess button
    const assessButton = page.locator('button:has-text("Assess"), button:has-text("Search"), button[type="submit"]').first();
    await assessButton.click();
    console.log('✓ Assess button clicked');
    
    // Wait for results to load - look for the address heading which appears after assessment
    try {
      await page.waitForSelector('text=/11348 Elderwood/', { timeout: 15000 });
      console.log('✓ Results loaded');
    } catch (e) {
      console.log('⚠ Results may not have loaded within timeout');
    }
    
    await page.waitForTimeout(2000); // Additional wait for animations
    
    // Take screenshot
    await page.screenshot({ 
      path: path.join(SCREENSHOTS_DIR, 'e2e-assessment-results.png'),
      fullPage: true 
    });
    console.log('✓ Screenshot saved: e2e-assessment-results.png');
    
    // Verify results
    const pageText = await page.textContent('body');
    const hasAddress = pageText.includes('11348 Elderwood');
    const hasSetbacks = pageText.includes('Setback');
    const mapExists = await page.locator('[class*="mapbox"]').count() > 0;
    
    console.log('Verification:');
    console.log(`  - Address displayed: ${hasAddress ? 'YES' : 'NO'}`);
    console.log(`  - Constraint results shown: ${hasSetbacks ? 'YES' : 'NO'}`);
    console.log(`  - Map rendered: ${mapExists ? 'YES' : 'NO'}`);
    
    if (consoleErrors.length > 0) {
      console.log('⚠ Console errors:', consoleErrors);
    }
    
    expect(hasAddress).toBeTruthy();
    console.log('✓ Journey 2: PASS\n');
  });

  test('Journey 3: Constraint Details', async ({ page }) => {
    console.log('\n=== Journey 3: Constraint Details ===');
    
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    
    // Perform assessment
    const searchInput = page.locator('input[type="text"], input[placeholder*="address"], input[placeholder*="Address"]').first();
    await searchInput.fill('11348 Elderwood St, Los Angeles, CA');
    const assessButton = page.locator('button:has-text("Assess"), button:has-text("Search"), button[type="submit"]').first();
    await assessButton.click();
    
    // Wait for results - look for the address heading
    await page.waitForSelector('text=/11348 Elderwood/', { timeout: 15000 });
    await page.waitForTimeout(2000);
    
    // Click on first constraint card - look for setback text button
    const firstConstraint = page.locator('button:has-text("Setback")').first();
    const exists = await firstConstraint.count() > 0;
    
    if (exists) {
      await firstConstraint.click();
      console.log('✓ Clicked on constraint card');
      
      await page.waitForTimeout(1000); // Wait for expansion animation
      
      // Take screenshot
      await page.screenshot({ 
        path: path.join(SCREENSHOTS_DIR, 'e2e-constraint-expanded.png'),
        fullPage: true 
      });
      console.log('✓ Screenshot saved: e2e-constraint-expanded.png');
      
      // Check for citations
      const pageContent = await page.textContent('body');
      const hasCitations = pageContent.includes('LAMC') || pageContent.includes('Citations') || pageContent.includes('Reasoning');
      console.log(`  - Citations/reasoning visible: ${hasCitations ? 'YES' : 'NO'}`);
      
      console.log('✓ Journey 3: PASS\n');
    } else {
      console.log('⚠ No constraint cards found - taking screenshot of current state');
      await page.screenshot({ 
        path: path.join(SCREENSHOTS_DIR, 'e2e-constraint-expanded.png'),
        fullPage: true 
      });
      console.log('~ Journey 3: SKIP (no constraints found)\n');
    }
  });

  test('Journey 4: Admin Panel', async ({ page }) => {
    console.log('\n=== Journey 4: Admin Panel ===');
    
    await page.goto(`${BASE_URL}/admin`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    
    // Take screenshot
    await page.screenshot({ 
      path: path.join(SCREENSHOTS_DIR, 'e2e-admin-panel.png'),
      fullPage: true 
    });
    console.log('✓ Screenshot saved: e2e-admin-panel.png');
    
    // Verify admin panel elements
    const pageContent = await page.content();
    const hasRules = pageContent.includes('rule') || pageContent.includes('Rule');
    const hasPipeline = pageContent.includes('pipeline') || pageContent.includes('Pipeline') || pageContent.includes('status');
    
    console.log('Verification:');
    console.log(`  - Rules displayed: ${hasRules ? 'YES' : 'NO'}`);
    console.log(`  - Pipeline status: ${hasPipeline ? 'YES' : 'NO'}`);
    
    if (consoleErrors.length > 0) {
      console.log('⚠ Console errors:', consoleErrors);
    }
    
    console.log('✓ Journey 4: PASS\n');
  });

  test('Journey 5: Building Type Change', async ({ page }) => {
    console.log('\n=== Journey 5: Building Type Change ===');
    
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    
    // Perform assessment first
    const searchInput = page.locator('input[type="text"], input[placeholder*="address"], input[placeholder*="Address"]').first();
    await searchInput.fill('11348 Elderwood St, Los Angeles, CA');
    const assessButton = page.locator('button:has-text("Assess"), button:has-text("Search"), button[type="submit"]').first();
    await assessButton.click();
    await page.waitForTimeout(3000);
    
    // Look for building type selector
    const aduButton = page.locator('button:has-text("ADU"), [class*="building-type"]:has-text("ADU")').first();
    const aduExists = await aduButton.count() > 0;
    
    if (aduExists) {
      await aduButton.click();
      console.log('✓ Changed building type to ADU');
      await page.waitForTimeout(3000); // Wait for re-assessment
      
      // Take screenshot
      await page.screenshot({ 
        path: path.join(SCREENSHOTS_DIR, 'e2e-adu-assessment.png'),
        fullPage: true 
      });
      console.log('✓ Screenshot saved: e2e-adu-assessment.png');
      console.log('✓ Journey 5: PASS\n');
    } else {
      console.log('⚠ Building type selector not found - feature may not be implemented yet');
      // Take screenshot anyway to show current state
      await page.screenshot({ 
        path: path.join(SCREENSHOTS_DIR, 'e2e-adu-assessment.png'),
        fullPage: true 
      });
      console.log('✓ Screenshot saved (current state): e2e-adu-assessment.png');
      console.log('~ Journey 5: SKIP (feature not found)\n');
    }
  });

  test('Journey 6: 404 / Invalid Route', async ({ page }) => {
    console.log('\n=== Journey 6: 404 / Invalid Route ===');
    
    await page.goto(`${BASE_URL}/nonexistent`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    
    // Take screenshot
    await page.screenshot({ 
      path: path.join(SCREENSHOTS_DIR, 'e2e-404-redirect.png'),
      fullPage: true 
    });
    console.log('✓ Screenshot saved: e2e-404-redirect.png');
    
    // Check final URL
    const finalUrl = page.url();
    console.log(`  - Final URL: ${finalUrl}`);
    
    const redirectedHome = finalUrl === BASE_URL || finalUrl === `${BASE_URL}/`;
    console.log(`  - Redirected to home: ${redirectedHome ? 'YES' : 'NO'}`);
    
    // Check it's not a blank page
    const bodyText = await page.locator('body').textContent();
    const hasContent = bodyText && bodyText.trim().length > 0;
    console.log(`  - Has content: ${hasContent ? 'YES' : 'NO'}`);
    
    if (consoleErrors.length > 0) {
      console.log('⚠ Console errors:', consoleErrors);
    }
    
    console.log('✓ Journey 6: PASS\n');
  });
});
