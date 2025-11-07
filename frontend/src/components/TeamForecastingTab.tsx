import React, { useState } from 'react';
import {
    Box,
    Card,
    CardContent,
    Typography,
    TextField,
    Checkbox,
    FormControlLabel,
    FormGroup,
    Button,
    Slider,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableRow,
    Paper,
    Grid,
    Chip,
    Alert,
    CircularProgress,
    TableContainer
} from '@mui/material';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import axios from 'axios';

interface TeamForecast {
    team: string;
    total_hours: number;
    percentage: number;
    monthly_breakdown: Array<{
        month: number;
        phase: string;
        hours: number;
    }>;
}

interface ForecastResult {
    total_hours: number;
    estimated_months: number;
    teams: TeamForecast[];
    distribution_ratios: { [team: string]: number };
    baseline_set_used: string;
}

const TEAMS = ['BE Devs', 'FE Devs', 'Design', 'UX', 'PMs', 'Data'];

const PHASE_COLORS: { [key: string]: string } = {
    'Ramp Up': '#554DFF',
    'Busy (Peak)': '#00FFCE',
    'Ramp Down': '#7D00FF'
};

export const TeamForecastingTab = () => {
    // Form state
    const [totalHours, setTotalHours] = useState(500);
    const [estimatedMonths, setEstimatedMonths] = useState(6);
    const [beIntegrations, setBeIntegrations] = useState(false);
    const [customTheme, setCustomTheme] = useState(false);
    const [customDesigns, setCustomDesigns] = useState(false);
    const [uxResearch, setUxResearch] = useState(false);
    const [teamsSelected, setTeamsSelected] = useState<string[]>(['BE Devs', 'FE Devs', 'PMs']);

    // Results state
    const [forecast, setForecast] = useState<ForecastResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleTeamToggle = (team: string) => {
        setTeamsSelected(prev =>
            prev.includes(team) ? prev.filter(t => t !== team) : [...prev, team]
        );
    };

    const handleCalculate = async () => {
        if (teamsSelected.length === 0) {
            setError('Please select at least one team');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const response = await axios.post('/api/forecasts/calculate-from-total', {
                total_hours: totalHours,
                be_integrations: beIntegrations,
                custom_theme: customTheme,
                custom_designs: customDesigns,
                ux_research: uxResearch,
                teams_selected: teamsSelected,
                estimated_months: estimatedMonths
            });

            setForecast(response.data);
        } catch (err: any) {
            setError(err.response?.data?.error || err.message || 'Error calculating forecast');
        } finally {
            setLoading(false);
        }
    };

    const prepareChartData = () => {
        if (!forecast) return [];

        const chartData: any[] = [];

        for (let month = 1; month <= estimatedMonths; month++) {
            const monthData: any = { month: `Month ${month}` };

            forecast.teams.forEach(teamForecast => {
                const monthlyData = teamForecast.monthly_breakdown.find(m => m.month === month);
                if (monthlyData) {
                    monthData[teamForecast.team] = monthlyData.hours;
                }
            });

            chartData.push(monthData);
        }

        return chartData;
    };

    return (
        <Box>
            <Grid container spacing={3}>
                {/* Input Form */}
                <Grid item xs={12} md={4}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6" gutterBottom>
                                Project Configuration
                            </Typography>

                            <TextField
                                label="Total Hours Budget"
                                type="number"
                                value={totalHours}
                                onChange={(e) => setTotalHours(parseInt(e.target.value) || 0)}
                                fullWidth
                                margin="normal"
                                helperText="Total hours available for the project"
                            />

                            <Typography variant="subtitle1" sx={{ mt: 3, mb: 1, fontWeight: 600 }}>
                                Estimated Duration: {estimatedMonths} months
                            </Typography>

                            <Slider
                                value={estimatedMonths}
                                onChange={(_, value) => setEstimatedMonths(value as number)}
                                min={3}
                                max={18}
                                step={1}
                                marks
                                valueLabelDisplay="auto"
                                color="secondary"
                            />

                            <Typography variant="subtitle1" sx={{ mt: 3, mb: 1, fontWeight: 600 }}>
                                Project Characteristics
                            </Typography>

                            <FormGroup>
                                <FormControlLabel
                                    control={
                                        <Checkbox
                                            checked={beIntegrations}
                                            onChange={(e) => setBeIntegrations(e.target.checked)}
                                            color="primary"
                                        />
                                    }
                                    label="Backend Integrations Required"
                                />
                                <FormControlLabel
                                    control={
                                        <Checkbox
                                            checked={customTheme}
                                            onChange={(e) => setCustomTheme(e.target.checked)}
                                            color="primary"
                                        />
                                    }
                                    label="Custom Theme Development"
                                />
                                <FormControlLabel
                                    control={
                                        <Checkbox
                                            checked={customDesigns}
                                            onChange={(e) => setCustomDesigns(e.target.checked)}
                                            color="primary"
                                        />
                                    }
                                    label="Custom Designs Required"
                                />
                                <FormControlLabel
                                    control={
                                        <Checkbox
                                            checked={uxResearch}
                                            onChange={(e) => setUxResearch(e.target.checked)}
                                            color="primary"
                                        />
                                    }
                                    label="Extensive UX Research"
                                />
                            </FormGroup>

                            <Typography variant="subtitle1" sx={{ mt: 3, mb: 1, fontWeight: 600 }}>
                                Teams Involved
                            </Typography>

                            <FormGroup>
                                {TEAMS.map(team => (
                                    <FormControlLabel
                                        key={team}
                                        control={
                                            <Checkbox
                                                checked={teamsSelected.includes(team)}
                                                onChange={() => handleTeamToggle(team)}
                                                color="secondary"
                                            />
                                        }
                                        label={team}
                                    />
                                ))}
                            </FormGroup>

                            <Box sx={{ mt: 3 }}>
                                <Button
                                    variant="contained"
                                    color="primary"
                                    onClick={handleCalculate}
                                    disabled={loading || teamsSelected.length === 0 || !totalHours}
                                    fullWidth
                                >
                                    {loading ? <CircularProgress size={24} /> : 'Calculate Distribution'}
                                </Button>
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>

                {/* Results Display */}
                <Grid item xs={12} md={8}>
                    {error && (
                        <Alert severity="error" sx={{ mb: 2 }}>
                            {error}
                        </Alert>
                    )}

                    {forecast && (
                        <>
                            {/* Summary Card */}
                            <Card sx={{ mb: 3 }}>
                                <CardContent>
                                    <Typography variant="h6" gutterBottom>
                                        Team Distribution Summary
                                    </Typography>

                                    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
                                        <Chip
                                            label={`Total: ${forecast.total_hours.toFixed(0)} hours`}
                                            color="primary"
                                            sx={{ fontWeight: 600, fontSize: '1.1rem' }}
                                        />
                                        <Chip
                                            label={`${forecast.estimated_months} months`}
                                            color="secondary"
                                        />
                                        <Chip
                                            label={forecast.baseline_set_used.replace('_', ' ').toUpperCase()}
                                            variant="outlined"
                                        />
                                    </Box>

                                    <Alert severity={beIntegrations ? 'warning' : 'info'} sx={{ mb: 2 }}>
                                        {beIntegrations
                                            ? '⚠️ Backend integrations require more backend hours. Distribution adjusted accordingly.'
                                            : 'ℹ️ Distribution based on historical patterns. Design/UX front-load work in early months.'}
                                    </Alert>

                                    {/* Team Allocation Table */}
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell><strong>Team</strong></TableCell>
                                                <TableCell align="right"><strong>Hours</strong></TableCell>
                                                <TableCell align="right"><strong>% of Total</strong></TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {forecast.teams.map(team => (
                                                <TableRow key={team.team}>
                                                    <TableCell><strong>{team.team}</strong></TableCell>
                                                    <TableCell align="right">{team.total_hours.toFixed(1)}h</TableCell>
                                                    <TableCell align="right">{team.percentage.toFixed(1)}%</TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </CardContent>
                            </Card>

                            {/* Month-by-Month Chart */}
                            <Card sx={{ mb: 3 }}>
                                <CardContent>
                                    <Typography variant="h6" gutterBottom>
                                        Monthly Distribution
                                    </Typography>

                                    <ResponsiveContainer width="100%" height={300}>
                                        <BarChart data={prepareChartData()}>
                                            <CartesianGrid strokeDasharray="3 3" />
                                            <XAxis dataKey="month" />
                                            <YAxis label={{ value: 'Hours', angle: -90, position: 'insideLeft' }} />
                                            <Tooltip />
                                            <Legend />
                                            {forecast.teams.map((team, index) => (
                                                <Bar
                                                    key={team.team}
                                                    dataKey={team.team}
                                                    stackId="a"
                                                    fill={`hsl(${index * 60}, 70%, 50%)`}
                                                />
                                            ))}
                                        </BarChart>
                                    </ResponsiveContainer>
                                </CardContent>
                            </Card>

                            {/* Detailed Breakdown Table */}
                            <Card>
                                <CardContent>
                                    <Typography variant="h6" gutterBottom>
                                        Detailed Breakdown by Team & Phase
                                    </Typography>

                                    <TableContainer component={Paper} sx={{ maxHeight: 500 }}>
                                        <Table stickyHeader size="small">
                                            <TableHead>
                                                <TableRow>
                                                    <TableCell><strong>Team</strong></TableCell>
                                                    <TableCell align="right"><strong>Total</strong></TableCell>
                                                    <TableCell align="right"><strong>Ramp Up</strong></TableCell>
                                                    <TableCell align="right"><strong>Busy Peak</strong></TableCell>
                                                    <TableCell align="right"><strong>Ramp Down</strong></TableCell>
                                                </TableRow>
                                            </TableHead>
                                            <TableBody>
                                                {forecast.teams.map(team => {
                                                    const rampUp = team.monthly_breakdown
                                                        .filter(m => m.phase === 'Ramp Up')
                                                        .reduce((sum, m) => sum + m.hours, 0);
                                                    const busy = team.monthly_breakdown
                                                        .filter(m => m.phase === 'Busy (Peak)')
                                                        .reduce((sum, m) => sum + m.hours, 0);
                                                    const rampDown = team.monthly_breakdown
                                                        .filter(m => m.phase === 'Ramp Down')
                                                        .reduce((sum, m) => sum + m.hours, 0);

                                                    return (
                                                        <TableRow key={team.team}>
                                                            <TableCell><strong>{team.team}</strong></TableCell>
                                                            <TableCell align="right">{team.total_hours.toFixed(1)}h</TableCell>
                                                            <TableCell align="right" sx={{ color: PHASE_COLORS['Ramp Up'] }}>
                                                                {rampUp.toFixed(1)}h
                                                            </TableCell>
                                                            <TableCell align="right" sx={{ color: PHASE_COLORS['Busy (Peak)'] }}>
                                                                {busy.toFixed(1)}h
                                                            </TableCell>
                                                            <TableCell align="right" sx={{ color: PHASE_COLORS['Ramp Down'] }}>
                                                                {rampDown.toFixed(1)}h
                                                            </TableCell>
                                                        </TableRow>
                                                    );
                                                })}
                                            </TableBody>
                                        </Table>
                                    </TableContainer>
                                </CardContent>
                            </Card>
                        </>
                    )}

                    {!forecast && !error && (
                        <Card>
                            <CardContent>
                                <Typography variant="body1" color="textSecondary" align="center" sx={{ py: 8 }}>
                                    Configure your project parameters and click "Calculate Distribution" to see how hours should be allocated across teams and months based on historical patterns.
                                </Typography>
                            </CardContent>
                        </Card>
                    )}
                </Grid>
            </Grid>
        </Box>
    );
};
